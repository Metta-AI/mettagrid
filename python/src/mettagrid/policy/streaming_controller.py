from __future__ import annotations

import inspect
import json
import logging
import os
import queue
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect as ws_connect

from mettagrid.policy.policy import AgentPolicy, MultiAgentPolicy, PolicyEpisodeContext
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.simulator import Action, AgentObservation

logger = logging.getLogger(__name__)

DEFAULT_INITIAL_POLICY_SOURCE = """
def step(agent_id, observation, state, policy_env):
    return {"action": "noop"}
""".strip()
INITIAL_PATCH_TIMEOUT_SECONDS = 0.25
CONNECT_TIMEOUT_SECONDS = 5.0


class StreamingControllerPatchError(ValueError):
    pass


@dataclass
class StreamingDecision:
    action: str
    vibe: str | None = None
    infos: dict[str, Any] = field(default_factory=dict)
    logs: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class _CompiledStreamingPolicy:
    source: str
    step_fn: Any
    step_arity: int
    revision: int


class _StreamingControllerSession:
    def __init__(
        self,
        *,
        url: str,
        episode: PolicyEpisodeContext,
        policy_env_info: PolicyEnvInterface,
        policy_source: str,
        policy_revision: int,
        connect_timeout_seconds: float,
        api_key: str | None = None,
    ) -> None:
        additional_headers = None
        if api_key:
            additional_headers = [("Authorization", f"Bearer {api_key}")]
        self._ws = ws_connect(url, open_timeout=connect_timeout_seconds, additional_headers=additional_headers)
        self._send_lock = threading.Lock()
        self._closed = threading.Event()
        self._patches: queue.SimpleQueue[dict[str, Any]] = queue.SimpleQueue()
        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._recv_thread.start()
        self.send_json(
            {
                "kind": "episode_hello",
                "episode_id": episode.episode_id,
                "agent_ids": list(episode.agent_ids),
                "observations_format": episode.observations_format,
                "game_rule_actions": list(episode.game_rule_actions),
                "policy_env": policy_env_info.model_dump(mode="json"),
                "policy_source": policy_source,
                "policy_revision": policy_revision,
            }
        )

    def _recv_loop(self) -> None:
        try:
            while not self._closed.is_set():
                message = self._ws.recv()
                if not isinstance(message, str):
                    continue
                payload = json.loads(message)
                if payload.get("kind") == "patch":
                    self._patches.put(payload)
        except ConnectionClosed:
            return
        except (EOFError, OSError, json.JSONDecodeError) as exc:
            if not self._closed.is_set():
                logger.warning("Streaming controller receive loop failed: %s", exc)

    def send_json(self, payload: dict[str, Any]) -> None:
        try:
            with self._send_lock:
                self._ws.send(json.dumps(payload))
        except (ConnectionClosed, EOFError, OSError) as exc:
            logger.warning("Streaming controller send failed: %s", exc)

    def wait_for_patches(self, timeout_seconds: float) -> list[dict[str, Any]]:
        deadline = time.monotonic() + timeout_seconds
        patches = self.drain_patches()
        while not patches and time.monotonic() < deadline:
            time.sleep(0.01)
            patches = self.drain_patches()
        return patches

    def drain_patches(self) -> list[dict[str, Any]]:
        patches: list[dict[str, Any]] = []
        while True:
            try:
                patches.append(self._patches.get_nowait())
            except queue.Empty:
                return patches

    def close(self, episode_id: str) -> None:
        self._closed.set()
        self.send_json({"kind": "episode_done", "episode_id": episode_id})
        self._ws.close()
        self._recv_thread.join(timeout=1)


class StreamingControllerPolicy(MultiAgentPolicy):
    short_names = ["streaming-controller"]

    def __init__(
        self,
        policy_env_info: PolicyEnvInterface,
        device: str = "cpu",
        *,
        controller_url: str | None = None,
        controller_url_env: str | None = "METTAGRID_CONTROLLER_URL",
        controller_api_key_env: str | None = "METTAGRID_CONTROLLER_API_KEY",
        initial_policy_source: str | None = None,
        initial_policy_path: str | None = None,
        controller_connect_timeout_seconds: float | str = CONNECT_TIMEOUT_SECONDS,
        initial_patch_timeout_seconds: float | str = INITIAL_PATCH_TIMEOUT_SECONDS,
    ) -> None:
        super().__init__(policy_env_info, device=device)
        self._controller_url = controller_url
        self._controller_url_env = controller_url_env
        self._controller_api_key_env = controller_api_key_env
        self._controller_connect_timeout_seconds = float(controller_connect_timeout_seconds)
        self._initial_patch_timeout_seconds = float(initial_patch_timeout_seconds)
        if initial_policy_path is not None:
            initial_policy_source = Path(initial_policy_path).read_text()
        resolved_initial_source = initial_policy_source or DEFAULT_INITIAL_POLICY_SOURCE
        self._policy = _compile_policy_source(resolved_initial_source, revision=0)
        self._last_good_policy = self._policy
        self._agents: dict[int, StreamingControllerAgentPolicy] = {}
        self._episode_context: PolicyEpisodeContext | None = None
        self._episode_state: dict[str, Any] = {}
        self._next_event_id = 0
        self._session: _StreamingControllerSession | None = None

    def prepare_episode(self, episode: PolicyEpisodeContext) -> None:
        self._close_session()
        self._episode_context = episode
        self._episode_state = {}
        self._next_event_id = 0
        controller_url = self._resolved_controller_url()
        if controller_url is None:
            return
        api_key = self._resolved_api_key()
        try:
            self._session = _StreamingControllerSession(
                url=controller_url,
                episode=episode,
                policy_env_info=self.policy_env_info,
                policy_source=self._policy.source,
                policy_revision=self._policy.revision,
                connect_timeout_seconds=self._controller_connect_timeout_seconds,
                api_key=api_key,
            )
        except OSError as exc:
            logger.warning("Failed to connect streaming controller at %s: %s", controller_url, exc)
            self._session = None
            return
        self._apply_patch_payloads(self._session.wait_for_patches(self._initial_patch_timeout_seconds))

    def close_episode(self, episode: PolicyEpisodeContext) -> None:
        if self._episode_context is None or self._episode_context.episode_id != episode.episode_id:
            return
        self._close_session()
        self._episode_context = None
        self._episode_state = {}

    def agent_policy(self, agent_id: int) -> AgentPolicy:
        if agent_id not in self._agents:
            self._agents[agent_id] = StreamingControllerAgentPolicy(self, agent_id)
        return self._agents[agent_id]

    def _resolved_controller_url(self) -> str | None:
        if self._controller_url:
            return self._controller_url
        if self._controller_url_env is None:
            return None
        return os.environ.get(self._controller_url_env)

    def _resolved_api_key(self) -> str | None:
        if self._controller_api_key_env is None:
            return None
        return os.environ.get(self._controller_api_key_env)

    def _close_session(self) -> None:
        if self._session is None or self._episode_context is None:
            self._session = None
            return
        self._session.close(self._episode_context.episode_id)
        self._session = None

    def _apply_pending_patches(self) -> None:
        if self._session is None:
            return
        self._apply_patch_payloads(self._session.drain_patches())

    def _apply_patch_payloads(self, patches: list[dict[str, Any]]) -> None:
        for patch in patches:
            next_source = patch.get("set_policy")
            if not isinstance(next_source, str):
                continue
            try:
                self._policy = _compile_policy_source(next_source, revision=self._policy.revision + 1)
            except StreamingControllerPatchError as exc:
                logger.warning("Rejected controller patch: %s", exc)

    def _execute_current_policy(self, agent_id: int, observation_payload: dict[str, Any]) -> StreamingDecision:
        raw_decision = _invoke_step_fn(self._policy, agent_id, observation_payload, self._episode_state, self)
        return _coerce_decision(raw_decision)

    def _step(self, agent_id: int, obs: AgentObservation) -> StreamingDecision:
        self._apply_pending_patches()
        observation_payload = _serialize_observation(obs)
        try:
            decision = self._execute_current_policy(agent_id, observation_payload)
        except Exception as exc:
            if self._policy is self._last_good_policy:
                raise
            logger.warning("Controller patch crashed during step; reverting to last good policy: %s", exc)
            self._policy = self._last_good_policy
            decision = self._execute_current_policy(agent_id, observation_payload)
        self._last_good_policy = self._policy
        if self._session is not None and self._episode_context is not None:
            self._session.send_json(
                {
                    "kind": "step",
                    "episode_id": self._episode_context.episode_id,
                    "event_id": self._next_event_id,
                    "agent_id": agent_id,
                    "observation": observation_payload,
                    "decision": {"action": decision.action, "vibe": decision.vibe},
                    "infos": decision.infos,
                    "logs": decision.logs,
                    "policy_revision": self._policy.revision,
                }
            )
            self._next_event_id += 1
        self._apply_pending_patches()
        return decision


class StreamingControllerAgentPolicy(AgentPolicy):
    def __init__(self, parent: StreamingControllerPolicy, agent_id: int) -> None:
        super().__init__(parent.policy_env_info)
        self._parent = parent
        self._agent_id = agent_id

    def step(self, obs: AgentObservation) -> Action:
        decision = self._parent._step(self._agent_id, obs)
        self._infos = decision.infos
        return Action(name=decision.action, vibe=decision.vibe)


def _compile_policy_source(source: str, *, revision: int) -> _CompiledStreamingPolicy:
    namespace: dict[str, Any] = {}
    exec(compile(source, "<streaming-controller-policy>", "exec"), namespace, namespace)
    step_fn = namespace.get("step")
    if not callable(step_fn):
        raise StreamingControllerPatchError("policy source must define callable step(...)")
    step_arity = len(inspect.signature(step_fn).parameters)
    if step_arity not in (3, 4):
        raise StreamingControllerPatchError("policy step must accept step(agent_id, observation, state[, policy_env])")
    return _CompiledStreamingPolicy(source=source, step_fn=step_fn, step_arity=step_arity, revision=revision)


def _invoke_step_fn(
    compiled_policy: _CompiledStreamingPolicy,
    agent_id: int,
    observation: dict[str, Any],
    state: dict[str, Any],
    controller_policy: StreamingControllerPolicy,
) -> Any:
    if compiled_policy.step_arity == 3:
        return compiled_policy.step_fn(agent_id, observation, state)
    return compiled_policy.step_fn(agent_id, observation, state, controller_policy.policy_env_info)


def _coerce_decision(raw_decision: Any) -> StreamingDecision:
    if isinstance(raw_decision, Action):
        return StreamingDecision(action=raw_decision.name, vibe=raw_decision.vibe)
    if isinstance(raw_decision, str):
        return StreamingDecision(action=raw_decision)
    if not isinstance(raw_decision, dict):
        raise StreamingControllerPatchError(f"policy step returned unsupported decision {raw_decision!r}")
    action = raw_decision.get("action")
    if not isinstance(action, str):
        raise StreamingControllerPatchError("policy step must return an action name")
    vibe = raw_decision.get("vibe")
    if vibe is not None and not isinstance(vibe, str):
        raise StreamingControllerPatchError("policy step returned non-string vibe")
    infos = raw_decision.get("infos", {})
    if not isinstance(infos, dict):
        raise StreamingControllerPatchError("policy step returned non-dict infos")
    logs = raw_decision.get("logs", [])
    if not isinstance(logs, list):
        raise StreamingControllerPatchError("policy step returned non-list logs")
    return StreamingDecision(action=action, vibe=vibe, infos=infos, logs=logs)


def _serialize_observation(obs: AgentObservation) -> dict[str, Any]:
    return {
        "agent_id": obs.agent_id,
        "tokens": [
            {
                "feature_id": token.feature.id,
                "feature_name": token.feature.name,
                "value": token.value,
                "raw_token": list(token.raw_token),
            }
            for token in obs.tokens
        ],
    }
