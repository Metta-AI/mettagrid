from __future__ import annotations

import asyncio
import itertools
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from mettagrid.config.mettagrid_config import MettaGridConfig
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.simulator import Simulator

PLAYER_PROTOCOL = "coworld.player.v1"
TickMode = Literal["fixed", "tick_when_act"]


class PlayerWebSocket(Protocol):
    async def send_json(self, data: Mapping[str, Any]) -> None: ...

    async def close(self, code: int = 1000, reason: str | None = None) -> None: ...


class PlayerClientMessage(BaseModel):
    type: Literal["action", "takeover", "release_takeover"]
    action_name: str | None = None
    action_index: int | None = None
    policy_infos: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None


@dataclass(frozen=True)
class SubmittedAction:
    action_index: int
    action_name: str
    connection_id: str
    policy_infos: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None

    def as_state(self) -> dict[str, Any]:
        return {
            "action_index": self.action_index,
            "action_name": self.action_name,
            "connection_id": self.connection_id,
            "policy_infos": self.policy_infos,
            "request_id": self.request_id,
        }


@dataclass(frozen=True)
class LivePlayerConnection:
    connection_id: str
    slot: int
    websocket: PlayerWebSocket


class LiveMettaGridEpisode:
    def __init__(
        self,
        sim: Any,
        policy_env: PolicyEnvInterface,
        *,
        tokens: list[str],
        max_steps: int,
        step_seconds: float,
        message_context: Mapping[str, Any] | None = None,
        start_grace_seconds: float = 0.5,
        tick_mode: TickMode = "fixed",
        human_action_timeout_seconds: float = 5.0,
        wait_for_all_players: bool = False,
        policy_action_timeout_seconds: float | None = None,
        initial_policy_action_timeout_seconds: float | None = None,
        disconnect_exception_types: tuple[type[Exception], ...] = (RuntimeError,),
        request_shutdown: Callable[[], None] = lambda: None,
        autostart: bool = True,
    ):
        self.sim = sim
        self.policy_env = policy_env
        self.tokens = tokens
        self.max_steps = max_steps
        self.step_seconds = step_seconds
        self.message_context = dict(message_context or {})
        self.start_grace_seconds = start_grace_seconds
        self.tick_mode: TickMode = tick_mode
        self.human_action_timeout_seconds = human_action_timeout_seconds
        self.wait_for_all_players = wait_for_all_players
        self.policy_action_timeout_seconds = policy_action_timeout_seconds
        self.initial_policy_action_timeout_seconds = initial_policy_action_timeout_seconds
        self.disconnect_exception_types = disconnect_exception_types
        self.request_shutdown = request_shutdown
        self.autostart = autostart

        self.action_names = list(policy_env.action_names)
        self.noop_action_index = self.action_names.index("noop")
        self._noop_action = SubmittedAction(
            action_index=self.noop_action_index,
            action_name=self.action_names[self.noop_action_index],
            connection_id="system",
        )
        self.latest_policy_actions = [self._noop_action for _ in tokens]
        self.latest_human_actions: dict[int, SubmittedAction] = {}
        self.pending_human_actions: dict[int, SubmittedAction] = {}
        self.latest_action_indices = [self.noop_action_index for _ in tokens]

        self.connections: dict[str, LivePlayerConnection] = {}
        self.connections_by_slot: dict[int, dict[str, LivePlayerConnection]] = {slot: {} for slot in range(len(tokens))}
        self.human_controller_connection_ids: dict[int, str | None] = {slot: None for slot in range(len(tokens))}
        self._connection_ids = (f"player-{idx}" for idx in itertools.count())
        self._human_action_event = asyncio.Event()
        self._policy_action_event = asyncio.Event()

        self.play_task: asyncio.Task[None] | None = None
        self.done = False
        self.paused = False
        self.start_deadline: float | None = None
        self.replay_events: list[dict[str, Any]] = []
        self._results_path: Path | None = None
        self._replay_path: Path | None = None
        self._results_builder: Callable[[], dict[str, Any]] | None = None
        self._replay_step_builder: Callable[[], dict[str, Any]] | None = None

    @classmethod
    def from_env(
        cls,
        env: MettaGridConfig,
        *,
        seed: int,
        tokens: list[str],
        max_steps: int,
        step_seconds: float,
        message_context: Mapping[str, Any] | None = None,
        start_grace_seconds: float = 0.5,
        tick_mode: TickMode = "fixed",
        human_action_timeout_seconds: float = 5.0,
        wait_for_all_players: bool = False,
        policy_action_timeout_seconds: float | None = None,
        initial_policy_action_timeout_seconds: float | None = None,
        disconnect_exception_types: tuple[type[Exception], ...] = (RuntimeError,),
        request_shutdown: Callable[[], None] = lambda: None,
        autostart: bool = True,
    ) -> "LiveMettaGridEpisode":
        sim = Simulator().new_simulation(env, seed=seed)
        return cls(
            sim,
            PolicyEnvInterface.from_mg_cfg(sim.config),
            tokens=tokens,
            max_steps=max_steps,
            step_seconds=step_seconds,
            message_context=message_context,
            start_grace_seconds=start_grace_seconds,
            tick_mode=tick_mode,
            human_action_timeout_seconds=human_action_timeout_seconds,
            wait_for_all_players=wait_for_all_players,
            policy_action_timeout_seconds=policy_action_timeout_seconds,
            initial_policy_action_timeout_seconds=initial_policy_action_timeout_seconds,
            disconnect_exception_types=disconnect_exception_types,
            request_shutdown=request_shutdown,
            autostart=autostart,
        )

    def configure_artifacts(
        self,
        *,
        results_path: Path,
        replay_path: Path | None,
        results_builder: Callable[[], dict[str, Any]],
    ) -> None:
        self._results_path = results_path
        self._replay_path = replay_path
        self._results_builder = results_builder

    def configure_replay_events(
        self,
        *,
        baseline_builder: Callable[[], dict[str, Any]],
        step_builder: Callable[[], dict[str, Any]],
    ) -> None:
        self.replay_events = [baseline_builder()]
        self._replay_step_builder = step_builder

    async def connect_player(self, slot: int, websocket: PlayerWebSocket) -> str:
        connection_id = next(self._connection_ids)
        connection = LivePlayerConnection(connection_id=connection_id, slot=slot, websocket=websocket)
        await websocket.send_json(self.player_config_message(slot, connection_id))
        self.connections[connection_id] = connection
        self.connections_by_slot[slot][connection_id] = connection
        if self.autostart:
            self._start_when_ready()
        return connection_id

    def disconnect_player(self, connection_id: str) -> None:
        connection = self.connections.pop(connection_id, None)
        if connection is None:
            return
        del self.connections_by_slot[connection.slot][connection_id]
        if self.human_controller_connection_ids[connection.slot] == connection_id:
            self.release_takeover(connection.slot)
        self._human_action_event.set()
        self._policy_action_event.set()

    async def boot_connection(self, connection_id: str) -> None:
        connection = self.connections.get(connection_id)
        if connection is None:
            return
        await connection.websocket.close(code=4000, reason="booted by admin")
        self.disconnect_player(connection_id)

    def _start_when_ready(self) -> None:
        if self.play_task is not None:
            return
        if len(self.connected_slots()) == len(self.tokens):
            self.play_task = asyncio.create_task(self.run())
            return
        if self.wait_for_all_players:
            return
        self.start_deadline = asyncio.get_running_loop().time() + self.start_grace_seconds
        self.play_task = asyncio.create_task(self._run_after_grace())

    async def _run_after_grace(self) -> None:
        while len(self.connected_slots()) < len(self.tokens):
            assert self.start_deadline is not None
            delay = self.start_deadline - asyncio.get_running_loop().time()
            if delay <= 0:
                break
            await asyncio.sleep(min(delay, 0.05))
        await self.run()

    def connected_slots(self) -> set[int]:
        return {connection.slot for connection in self.connections.values()}

    async def handle_player_message(self, connection_id: str, raw_message: Mapping[str, Any]) -> None:
        connection = self.connections.get(connection_id)
        if connection is None:
            return
        message = PlayerClientMessage.model_validate(raw_message)
        if message.type == "takeover":
            self.takeover(connection.slot, connection_id)
            await connection.websocket.send_json(self.player_config_message(connection.slot, connection_id))
            return
        if message.type == "release_takeover":
            self.release_takeover(connection.slot, connection_id)
            await connection.websocket.send_json(self.player_config_message(connection.slot, connection_id))
            return

        action = self._submitted_action(connection_id, message)
        if self.human_controller_connection_ids[connection.slot] == connection_id:
            self.pending_human_actions[connection.slot] = action
            self.latest_human_actions[connection.slot] = action
            self._human_action_event.set()
        else:
            self.latest_policy_actions[connection.slot] = action
            self._policy_action_event.set()

    def set_policy_action(self, slot: int, raw_message: Mapping[str, Any], *, connection_id: str = "policy") -> None:
        message = PlayerClientMessage.model_validate({**raw_message, "type": "action"})
        self.latest_policy_actions[slot] = self._submitted_action(connection_id, message)
        self._policy_action_event.set()

    def takeover(self, slot: int, connection_id: str) -> None:
        if connection_id not in self.connections_by_slot[slot]:
            raise ValueError(f"Connection {connection_id!r} is not attached to slot {slot}")
        self.human_controller_connection_ids[slot] = connection_id
        self.tick_mode = "tick_when_act"
        self.pending_human_actions.pop(slot, None)

    def release_takeover(self, slot: int, connection_id: str | None = None) -> None:
        active_connection_id = self.human_controller_connection_ids[slot]
        if connection_id is not None and active_connection_id != connection_id:
            return
        self.human_controller_connection_ids[slot] = None
        self.pending_human_actions.pop(slot, None)

    async def run(self) -> None:
        while self.sim.current_step < self.max_steps and not self.sim.is_done():
            if self.paused:
                await asyncio.sleep(0.05)
                continue
            self._human_action_event.clear()
            self._policy_action_event.clear()
            step = self.sim.current_step
            await self.send_observations()
            await self._wait_for_next_tick(step)
            self.apply_actions(step)
            self.sim.step()
            if self._replay_step_builder is not None:
                self.replay_events.append(self._replay_step_builder())

        self.done = True
        results = self.results()
        if self._results_path is not None:
            self._results_path.write_text(json.dumps(results))
        if self._replay_path is not None:
            self._replay_path.write_text(json.dumps({"events": self.replay_events, "results": results}))
        await self.send_final()
        await asyncio.sleep(0.2)
        self.request_shutdown()

    async def _wait_for_next_tick(self, step: int) -> None:
        policy_action_timeout_seconds = (
            self.initial_policy_action_timeout_seconds
            if step == 0 and self.initial_policy_action_timeout_seconds is not None
            else self.policy_action_timeout_seconds
        )
        if policy_action_timeout_seconds is not None:
            await self._wait_for_policy_actions(step, policy_action_timeout_seconds)
            if not (self.tick_mode == "tick_when_act" and any(self.human_controller_connection_ids.values())):
                await asyncio.sleep(self.step_seconds)
                return
        if self.tick_mode == "tick_when_act" and any(self.human_controller_connection_ids.values()):
            await self._wait_for_event(self._human_action_event, self.human_action_timeout_seconds)
            return
        await asyncio.sleep(self.step_seconds)

    async def _wait_for_policy_actions(self, step: int, timeout_seconds: float) -> None:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while not self._policy_actions_ready(step):
            self._policy_action_event.clear()
            if self._policy_actions_ready(step):
                break
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                break
            await self._wait_for_event(self._policy_action_event, remaining)

    async def _wait_for_event(self, event: asyncio.Event, timeout_seconds: float) -> None:
        waiter = asyncio.create_task(event.wait())
        done, pending = await asyncio.wait({waiter}, timeout=timeout_seconds)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            task.result()

    def _policy_actions_ready(self, step: int) -> bool:
        expected_request_id = f"step-{step}"
        return all(
            not self.connections_by_slot[slot]
            or self.human_controller_connection_ids[slot] is not None
            or self.latest_policy_actions[slot].request_id == expected_request_id
            for slot in range(len(self.tokens))
        )

    async def send_observations(self) -> None:
        await self._send_to_players(
            {
                connection_id: self.observation_message(connection.slot)
                for connection_id, connection in self.connections.items()
            }
        )

    async def send_final(self) -> None:
        final_message = {**self.snapshot(), "type": "final"}
        await self._send_to_players({connection_id: final_message for connection_id in self.connections})

    async def _send_to_players(self, messages: dict[str, dict[str, Any]]) -> None:
        connections = tuple(
            (connection_id, self.connections[connection_id])
            for connection_id in messages
            if connection_id in self.connections
        )
        results = await asyncio.gather(
            *(connection.websocket.send_json(messages[connection_id]) for connection_id, connection in connections),
            return_exceptions=True,
        )
        for (connection_id, _connection), result in zip(connections, results, strict=True):
            if isinstance(result, self.disconnect_exception_types):
                self.disconnect_player(connection_id)
            elif isinstance(result, Exception):
                raise result

    def apply_actions(self, step: int | None = None) -> None:
        for slot in range(len(self.tokens)):
            action = self._applied_action(slot, step)
            self.latest_action_indices[slot] = action.action_index
            self.sim.agent(slot).set_action(action.action_name)
        self.pending_human_actions.clear()

    def _applied_action(self, slot: int, step: int | None) -> SubmittedAction:
        if self.human_controller_connection_ids[slot] is None:
            if self.policy_action_timeout_seconds is not None and step is not None:
                action = self.latest_policy_actions[slot]
                if action.request_id != f"step-{step}":
                    return self._noop_action
            return self.latest_policy_actions[slot]
        return self.pending_human_actions.get(slot, self._noop_action)

    def player_config_message(self, slot: int, connection_id: str) -> dict[str, Any]:
        return {
            **self.message_context,
            "type": "player_config",
            "protocol": PLAYER_PROTOCOL,
            "slot": slot,
            "connection_id": connection_id,
            "num_agents": len(self.tokens),
            "action_names": self.action_names,
            "observation_shape": list(self.policy_env.observation_shape),
            "policy_env": self.policy_env.model_dump(mode="json"),
            "observation": self.observation_metadata(),
            "control_state": self.slot_control_state(slot),
        }

    def observation_message(self, slot: int) -> dict[str, Any]:
        return {
            **self.message_context,
            "type": "observation",
            "protocol": PLAYER_PROTOCOL,
            "slot": slot,
            "step": self.sim.current_step,
            "observation": self.sim._c_sim.observations()[slot].tolist(),
            "scores": self.scores(),
            "is_human_controlled": self.human_controller_connection_ids[slot] is not None,
            "control_state": self.slot_control_state(slot),
        }

    def observation_metadata(self) -> dict[str, Any]:
        return {
            "width": self.policy_env.obs_width,
            "height": self.policy_env.obs_height,
            "features": [
                {"id": feature.id, "name": feature.name, "normalization": feature.normalization}
                for feature in self.policy_env.obs_features
            ],
            "tags": self.policy_env.tags,
            "global_location": 254,
            "empty_location": 255,
        }

    def slot_control_state(self, slot: int) -> dict[str, Any]:
        human_controller_connection_id = self.human_controller_connection_ids[slot]
        return {
            "control_mode": "human" if human_controller_connection_id is not None else "policy",
            "human_controller_connection_id": human_controller_connection_id,
            "tick_mode": self.tick_mode,
            "human_action_timeout_seconds": self.human_action_timeout_seconds,
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            **self.message_context,
            "type": "state",
            "protocol": PLAYER_PROTOCOL,
            "step": self.sim.current_step,
            "done": self.done,
            "paused": self.paused,
            "step_seconds": self.step_seconds,
            "tick_mode": self.tick_mode,
            "human_action_timeout_seconds": self.human_action_timeout_seconds,
            "scores": self.scores(),
            "num_agents": len(self.tokens),
            "connected_players": len(self.connections),
            "action_names": self.action_names,
            "slots": [self.slot_state(slot) for slot in range(len(self.tokens))],
        }

    def slot_state(self, slot: int) -> dict[str, Any]:
        return {
            "slot": slot,
            "control_state": self.slot_control_state(slot),
            "connections": [
                {"connection_id": connection_id} for connection_id in sorted(self.connections_by_slot[slot])
            ],
            "latest_policy_action": self.latest_policy_actions[slot].as_state(),
            "latest_human_action": (
                self.latest_human_actions[slot].as_state() if slot in self.latest_human_actions else None
            ),
            "applied_action_index": self.latest_action_indices[slot],
            "applied_action_name": self.action_names[self.latest_action_indices[slot]],
        }

    def scores(self) -> list[float]:
        return [float(score) for score in self.sim.episode_rewards.tolist()]

    def results(self) -> dict[str, Any]:
        if self._results_builder is None:
            return {"scores": self.scores(), "steps": self.sim.current_step}
        return self._results_builder()

    def _submitted_action(self, connection_id: str, message: PlayerClientMessage) -> SubmittedAction:
        action_index = self._action_index(message)
        return SubmittedAction(
            action_index=action_index,
            action_name=self.action_names[action_index],
            connection_id=connection_id,
            policy_infos=message.policy_infos,
            request_id=message.request_id,
        )

    def _action_index(self, message: PlayerClientMessage) -> int:
        if message.action_name is not None:
            if message.action_name in self.action_names:
                return self.action_names.index(message.action_name)
            return self.noop_action_index
        if message.action_index is not None:
            return self._normalized_action_index(message.action_index)
        return self.noop_action_index

    def _normalized_action_index(self, action_index: int) -> int:
        if 0 <= action_index < len(self.action_names):
            return action_index
        return self.noop_action_index
