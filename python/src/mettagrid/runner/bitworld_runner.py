"""BitWorld game engine runner.

Runs a BitWorld game server as a subprocess and connects policies via WebSocket.
BitWorld protocol: 128x128 pixel frames (8192 bytes packed, 4 bits/pixel, 16-color palette),
1-byte action bitmasks (up/down/left/right/select/A/B).

Reward protocol: text messages on a separate /reward WebSocket, format:
  "reward <address> <accumulated_reward>\n" per player per tick.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import subprocess
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, parse_qsl, urlencode, urlparse, urlunparse

import numpy as np
import websocket
from pydantic import BaseModel, ConfigDict, Field

from mettagrid.bitworld import (
    BITWORLD_ACTION_COUNT,
    BITWORLD_ACTION_MASKS,
    BITWORLD_ACTION_NAMES,
    BITWORLD_DEFAULT_FRAME_STACK,
    FRAME_PIXELS,
    PLAYER_PATH,
    PROTOCOL_BYTES,
    REWARD_PATH,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    BitWorldEndpoint,
    BitWorldServerConfig,
    bitworld_input_mask_name,
    pack_chat_packet,
    pack_input_packet,
    parse_reward_packet,
)
from mettagrid.policy.policy import MultiAgentPolicy, PolicySpec
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.runner.policy_server.websocket_transport import PolicyStepError, WebSocketRawPolicyServerClient
from mettagrid.runner.types import PureSingleEpisodeJob, PureSingleEpisodeResult
from mettagrid.types import EpisodeStats
from mettagrid.util.uri_resolvers.schemes import parse_uri

logger = logging.getLogger(__name__)

SERVER_START_ATTEMPTS = 5
SERVER_START_GRACE_S = 0.1
MAX_FRAME_DRAIN = 128
DEBUG_STATS_ENV = "BITWORLD_DEBUG_STATS"
POLICY_RUNNER_QUERY_KEYS = {"frame_stack"}

BITWORLD_AMONG_THEM_AGENT_COUNT = 5
BITWORLD_GAME_NAME = "among_them"


class BitWorldGameConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    num_agents: int = Field(ge=1)
    max_steps: int = Field(ge=0)
    bitworld: BitWorldServerConfig = Field(default_factory=BitWorldServerConfig)


class BitWorldEnvConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    game: BitWorldGameConfig


@dataclass
class BitWorldConfig:
    binary_path: str | None = None
    host: str = "127.0.0.1"
    port: int = 8080
    seed: int = 0
    max_ticks: int = 10000
    num_players: int = BITWORLD_AMONG_THEM_AGENT_COUNT
    imposter_count: int = 1
    tasks_per_player: int | None = None
    task_complete_ticks: int | None = None
    connect_timeout_s: float = 10.0

    @classmethod
    def from_env_config(cls, config: dict[str, Any]) -> BitWorldConfig:
        env_config = BitWorldEnvConfig.model_validate(config)
        return cls(
            max_ticks=env_config.game.max_steps,
            num_players=env_config.game.num_agents,
            imposter_count=env_config.game.bitworld.imposter_count,
            tasks_per_player=env_config.game.bitworld.tasks_per_player,
            task_complete_ticks=env_config.game.bitworld.task_complete_ticks,
        )


@dataclass
class PlayerConnection:
    ws: websocket.WebSocket
    player_index: int
    address: str
    alive: bool = True
    observation_stack: np.ndarray | None = None
    queued_frames: list[bytes] = field(default_factory=list)


@dataclass(frozen=True)
class LoadedBitWorldPolicy:
    policy: MultiAgentPolicy
    frame_stack: int


@dataclass
class RewardState:
    rewards_by_address: dict[str, float] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)
    ws: websocket.WebSocket | None = None
    thread: threading.Thread | None = None
    stop_event: threading.Event = field(default_factory=threading.Event)


def _find_bitworld_binary(config: BitWorldConfig) -> Path:
    if config.binary_path:
        p = Path(config.binary_path)
        if p.exists():
            return p
        raise FileNotFoundError(f"BitWorld binary not found: {config.binary_path}")

    candidates = [
        Path("/opt/bitworld") / BITWORLD_GAME_NAME / BITWORLD_GAME_NAME,
        Path.home() / "bitworld" / BITWORLD_GAME_NAME / BITWORLD_GAME_NAME,
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        f"BitWorld binary for '{BITWORLD_GAME_NAME}' not found. Searched: {[str(c) for c in candidates]}"
    )


def _replay_path_from_uri(replay_uri: str | None) -> Path | None:
    if replay_uri is None:
        return None

    parsed = parse_uri(replay_uri, allow_none=False)
    if parsed.scheme != "file":
        raise ValueError(f"BitWorld replay URI must be file://, got: {replay_uri}")
    return parsed.local_path


def _start_server(binary_path: Path, config: BitWorldConfig, replay_path: Path | None = None) -> subprocess.Popen:
    server_config_fields = {
        "seed": config.seed,
        "maxTicks": config.max_ticks,
        "minPlayers": config.num_players,
        "imposterCount": config.imposter_count,
    }
    if config.tasks_per_player is not None:
        server_config_fields["tasksPerPlayer"] = config.tasks_per_player
    if config.task_complete_ticks is not None:
        server_config_fields["taskCompleteTicks"] = config.task_complete_ticks
    server_config = json.dumps(server_config_fields, separators=(",", ":"))
    cmd = [
        str(binary_path),
        f"--address:{config.host}",
        f"--port:{config.port}",
        f"--config:{server_config}",
    ]
    if replay_path is not None:
        cmd.append(f"--save-replay:{replay_path}")
    logger.info("Starting BitWorld server: %s", " ".join(cmd))
    return subprocess.Popen(
        cmd,
        cwd=str(binary_path.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _connect_websocket(
    config: BitWorldConfig,
    path: str,
    label: str,
    player_name: str | None = None,
) -> websocket.WebSocket:
    url = BitWorldEndpoint(address=config.host, port=config.port).websocket_url(path, player_name)
    deadline = time.monotonic() + config.connect_timeout_s
    last_error = None
    while time.monotonic() < deadline:
        ws = websocket.WebSocket()
        ws.settimeout(2.0)
        try:
            ws.connect(url)
            logger.info("Connected %s to %s", label, url)
            return ws
        except (ConnectionRefusedError, OSError, websocket.WebSocketException) as e:
            last_error = e
            time.sleep(0.1)
    raise ConnectionError(f"Could not connect BitWorld {label} at {url}: {last_error}")


def _reward_listener(state: RewardState) -> None:
    assert state.ws is not None
    while not state.stop_event.is_set():
        try:
            data = state.ws.recv()
        except websocket.WebSocketTimeoutException:
            continue
        except (websocket.WebSocketConnectionClosedException, ConnectionError, OSError):
            break
        if not isinstance(data, str):
            continue
        packet = parse_reward_packet(data)
        for entry in packet.entries:
            if entry.name == "reward":
                with state.lock:
                    state.rewards_by_address[entry.player] = float(entry.value)


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_server_on_free_port(
    binary_path: Path,
    config: BitWorldConfig,
    replay_path: Path | None = None,
) -> subprocess.Popen:
    for attempt in range(SERVER_START_ATTEMPTS):
        config.port = _pick_free_port()
        server_proc = _start_server(binary_path, config, replay_path)
        time.sleep(SERVER_START_GRACE_S)
        if server_proc.poll() is None:
            return server_proc

        stderr = server_proc.stderr.read().decode(errors="replace").strip() if server_proc.stderr is not None else ""
        logger.warning(
            "BitWorld server exited during startup on port %d (attempt %d/%d): %s",
            config.port,
            attempt + 1,
            SERVER_START_ATTEMPTS,
            stderr,
        )

    raise RuntimeError(f"BitWorld server failed to start after {SERVER_START_ATTEMPTS} port attempts")


def _build_bitworld_env_interface(
    frame_stack: int = BITWORLD_DEFAULT_FRAME_STACK,
    num_agents: int = 1,
) -> PolicyEnvInterface:
    import gymnasium as gym  # noqa: PLC0415

    obs_space = gym.spaces.Box(low=0, high=15, shape=(frame_stack, SCREEN_HEIGHT, SCREEN_WIDTH), dtype=np.uint8)
    act_space = gym.spaces.Discrete(BITWORLD_ACTION_COUNT)
    return PolicyEnvInterface.from_spaces(
        observation_space=obs_space,
        action_space=act_space,
        num_agents=num_agents,
        action_names=list(BITWORLD_ACTION_NAMES),
        observation_kind="pixels",
    )


def _bitworld_policy_env_interface(num_agents: int = 1) -> tuple[PolicyEnvInterface, int]:
    return _build_bitworld_env_interface(num_agents=num_agents), BITWORLD_DEFAULT_FRAME_STACK


def _unpack_frame(frame_data: bytes) -> np.ndarray:
    if len(frame_data) != PROTOCOL_BYTES:
        raise ValueError(f"BitWorld frames must be {PROTOCOL_BYTES} packed bytes, received {len(frame_data)}")
    packed = np.frombuffer(frame_data, dtype=np.uint8)
    frame = np.empty(FRAME_PIXELS, dtype=np.uint8)
    frame[0::2] = packed & 0x0F
    frame[1::2] = packed >> 4
    return frame.reshape(FRAME_PIXELS // SCREEN_WIDTH, SCREEN_WIDTH)


def unpack_frame(frame_data: bytes) -> np.ndarray:
    return _unpack_frame(frame_data)


def _stack_observation(conn: PlayerConnection, frame_data: bytes, frame_stack: int) -> np.ndarray:
    frame = _unpack_frame(frame_data)
    if conn.observation_stack is None:
        conn.observation_stack = np.repeat(frame[np.newaxis, :, :], frame_stack, axis=0)
    else:
        conn.observation_stack[:-1] = conn.observation_stack[1:]
        conn.observation_stack[-1] = frame
    return conn.observation_stack


def _accept_player_frame(conn: PlayerConnection, data: object) -> None:
    if isinstance(data, bytes) and len(data) == PROTOCOL_BYTES:
        conn.queued_frames.append(data)


def _receive_player_frame(conn: PlayerConnection) -> tuple[bytes | None, int]:
    if not conn.queued_frames:
        try:
            _accept_player_frame(conn, conn.ws.recv())
        except (BlockingIOError, websocket.WebSocketTimeoutException):
            return None, 0
        except (websocket.WebSocketConnectionClosedException, ConnectionError):
            conn.alive = False
            return None, 0

    previous_timeout = conn.ws.gettimeout()
    conn.ws.settimeout(0.0)
    try:
        for _ in range(MAX_FRAME_DRAIN):
            try:
                _accept_player_frame(conn, conn.ws.recv())
            except (BlockingIOError, websocket.WebSocketTimeoutException):
                break
            except (websocket.WebSocketConnectionClosedException, ConnectionError):
                conn.alive = False
                break
    finally:
        conn.ws.settimeout(previous_timeout)

    if not conn.queued_frames:
        return None, 0

    frame_advance = len(conn.queued_frames)
    frame_data = conn.queued_frames[-1]
    conn.queued_frames.clear()
    return frame_data, frame_advance


def _is_policy_server_uri(uri: str) -> bool:
    return urlparse(uri).scheme in {"ws", "wss"}


def _policy_uri_frame_stack(uri: str) -> int:
    values = parse_qs(urlparse(uri).query).get("frame_stack")
    if values:
        frame_stack = int(values[-1])
        if frame_stack < 1:
            raise ValueError(f"BitWorld frame_stack query parameter must be positive, got {frame_stack}")
        return frame_stack
    return BITWORLD_DEFAULT_FRAME_STACK


def _policy_uri_without_runner_query(uri: str) -> str:
    parsed = urlparse(uri)
    if not parsed.query:
        return uri
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key not in POLICY_RUNNER_QUERY_KEYS
        ]
    )
    return urlunparse(parsed._replace(query=query))


def _policy_agent_ids(assignments: list[int], policy_count: int) -> list[list[int]]:
    policy_agent_ids: list[list[int]] = [[] for _ in range(policy_count)]
    for agent_id, policy_index in enumerate(assignments):
        policy_agent_ids[policy_index].append(agent_id)
    return policy_agent_ids


def _load_bitworld_policy(uri: str, agent_ids: list[int], num_agents: int) -> LoadedBitWorldPolicy:
    frame_stack = _policy_uri_frame_stack(uri)
    if _is_policy_server_uri(uri):
        env_interface = _build_bitworld_env_interface(frame_stack, num_agents=num_agents)
        return LoadedBitWorldPolicy(
            WebSocketRawPolicyServerClient(env_interface, url=uri, agent_ids=agent_ids),
            frame_stack,
        )

    from mettagrid.policy.loader import initialize_or_load_policy  # noqa: PLC0415
    from mettagrid.util.uri_resolvers.schemes import policy_spec_from_uri  # noqa: PLC0415

    policy_uri = _policy_uri_without_runner_query(uri)
    policy_spec = PolicySpec(class_path=policy_uri) if "://" not in policy_uri else policy_spec_from_uri(policy_uri)
    env_interface = _build_bitworld_env_interface(frame_stack, num_agents=num_agents)
    return LoadedBitWorldPolicy(initialize_or_load_policy(env_interface, policy_spec), frame_stack)


def _policy_step_actions(
    policy: MultiAgentPolicy,
    observations: np.ndarray,
    actions: np.ndarray,
    agent_ids: list[int],
    frame_advances: np.ndarray | None = None,
) -> None:
    step_with_frame_advances = getattr(policy, "step_batch_for_agents_with_frame_advances", None)
    if step_with_frame_advances is not None and frame_advances is not None:
        step_with_frame_advances(agent_ids, observations, actions, frame_advances)
    elif isinstance(policy, WebSocketRawPolicyServerClient):
        policy.step_batch_for_agents(agent_ids, observations, actions)
    elif (step_batch_for_agents := getattr(policy, "step_batch_for_agents", None)) is not None:
        step_batch_for_agents(agent_ids, observations, actions)
    else:
        policy.step_batch(observations, actions)


def _policy_chat_messages(policy: MultiAgentPolicy, agent_ids: list[int]) -> list[str | None]:
    chat_provider = getattr(policy, "bitworld_chat_messages", None)
    if chat_provider is None:
        return [None] * len(agent_ids)

    messages = list(chat_provider(agent_ids))
    if len(messages) != len(agent_ids):
        raise PolicyStepError(
            f"BitWorld chat provider returned {len(messages)} messages for {len(agent_ids)} agent_ids"
        )
    for index, message in enumerate(messages):
        if message is not None and not isinstance(message, str):
            raise PolicyStepError(f"BitWorld chat provider returned non-string message for agent {agent_ids[index]}")
    return messages


def _policy_debug_stats(policy: MultiAgentPolicy, agent_ids: list[int]) -> list[dict[str, float]]:
    if os.getenv(DEBUG_STATS_ENV, "").lower() not in {"1", "true", "yes", "on"}:
        return [{} for _agent_id in agent_ids]

    debug_provider = getattr(policy, "bitworld_debug_stats", None)
    if debug_provider is None:
        return [{} for _agent_id in agent_ids]

    stats = list(debug_provider(agent_ids))
    if len(stats) != len(agent_ids):
        raise PolicyStepError(f"BitWorld debug provider returned {len(stats)} items for {len(agent_ids)} agent_ids")
    return stats


def _policy_action_masks_and_chats(
    policy: MultiAgentPolicy,
    observations: np.ndarray,
    agent_ids: list[int],
    frame_advances: np.ndarray | None = None,
) -> tuple[np.ndarray, list[str | None], list[dict[str, float]]]:
    actions = np.zeros((observations.shape[0],), dtype=np.int64)
    _policy_step_actions(policy, observations, actions, agent_ids, frame_advances)
    invalid_indices = np.flatnonzero((actions < 0) | (actions >= BITWORLD_ACTION_COUNT))
    if invalid_indices.size:
        batch_index = int(invalid_indices[0])
        raise PolicyStepError(
            f"BitWorld policy action index must be in [0, {BITWORLD_ACTION_COUNT}), "
            f"got {int(actions[batch_index])} at batch index {batch_index}"
        )
    return (
        BITWORLD_ACTION_MASKS[actions],
        _policy_chat_messages(policy, agent_ids),
        _policy_debug_stats(policy, agent_ids),
    )


def _policy_action_masks(policy: MultiAgentPolicy, observations: np.ndarray, agent_ids: list[int]) -> np.ndarray:
    action_masks, _chat_messages, _debug_stats = _policy_action_masks_and_chats(policy, observations, agent_ids)
    return action_masks


def _action_stat_key(action_mask: int) -> str:
    return f"action.{bitworld_input_mask_name(action_mask)}.success"


def run_bitworld_episode(job: PureSingleEpisodeJob) -> PureSingleEpisodeResult:
    config = BitWorldConfig.from_env_config(job.env.model_dump(mode="json"))
    config.seed = job.seed
    if len(job.assignments) != config.num_players:
        raise ValueError(
            f"BitWorld {BITWORLD_GAME_NAME} expects {config.num_players} assignments, got {len(job.assignments)}"
        )

    policies: list[LoadedBitWorldPolicy] = []
    policy_agent_ids = _policy_agent_ids(job.assignments, len(job.policy_uris))
    for policy_index, uri in enumerate(job.policy_uris):
        policies.append(_load_bitworld_policy(uri, policy_agent_ids[policy_index], config.num_players))

    binary_path = _find_bitworld_binary(config)
    replay_path = _replay_path_from_uri(job.replay_uri)
    server_proc = _start_server_on_free_port(binary_path, config, replay_path)

    connections: list[PlayerConnection] = []
    reward_state = RewardState()
    action_stats: list[defaultdict[str, float]] = [defaultdict(float) for _agent_id in range(config.num_players)]

    try:
        reward_state.ws = _connect_websocket(config, REWARD_PATH, "reward listener")
        reward_state.thread = threading.Thread(target=_reward_listener, args=(reward_state,), daemon=True)
        reward_state.thread.start()

        for i in range(config.num_players):
            address = f"player_{i}"
            ws = _connect_websocket(config, PLAYER_PATH, f"player {i}", player_name=address)
            connections.append(PlayerConnection(ws=ws, player_index=i, address=address))

        for _tick in range(config.max_ticks):
            all_dead = True
            pending_actions: list[tuple[PlayerConnection, LoadedBitWorldPolicy, np.ndarray, int]] = []
            for conn in connections:
                if not conn.alive:
                    continue
                all_dead = False

                frame_data, frame_advance = _receive_player_frame(conn)
                if frame_data is None:
                    continue

                loaded_policy = policies[job.assignments[conn.player_index]]
                observation = _stack_observation(conn, frame_data, loaded_policy.frame_stack)
                pending_actions.append((conn, loaded_policy, observation, frame_advance))

            for loaded_policy in policies:
                batch = [
                    (conn, observation, frame_advance)
                    for conn, policy_for_conn, observation, frame_advance in pending_actions
                    if policy_for_conn is loaded_policy
                ]
                if not batch:
                    continue
                observations = np.stack([observation for _conn, observation, _frame_advance in batch])
                agent_ids = [conn.player_index for conn, _observation, _frame_advance in batch]
                frame_advances = np.asarray(
                    [frame_advance for _conn, _observation, frame_advance in batch], dtype=np.int32
                )
                action_masks, chat_messages, debug_stats = _policy_action_masks_and_chats(
                    loaded_policy.policy, observations, agent_ids, frame_advances
                )
                for (conn, _observation), action_mask, chat_message, debug_stat in zip(
                    [(conn, observation) for conn, observation, _frame_advance in batch],
                    action_masks,
                    chat_messages,
                    debug_stats,
                    strict=True,
                ):
                    mask = int(action_mask)
                    conn.ws.send(pack_input_packet(mask), websocket.ABNF.OPCODE_BINARY)
                    action_stats[conn.player_index][_action_stat_key(mask)] += 1
                    action_stats[conn.player_index]["frame_advance.samples"] += 1
                    action_stats[conn.player_index]["frame_advance.total"] += float(frame_advance)
                    action_stats[conn.player_index]["frame_advance.max"] = max(
                        action_stats[conn.player_index]["frame_advance.max"],
                        float(frame_advance),
                    )
                    for name, value in debug_stat.items():
                        action_stats[conn.player_index][f"debug.{name}.last"] = float(value)
                    if chat_message is not None and chat_message.strip():
                        conn.ws.send(pack_chat_packet(chat_message), websocket.ABNF.OPCODE_BINARY)
                        action_stats[conn.player_index]["chat.sent"] += 1

            if all_dead:
                break

        with reward_state.lock:
            rewards_by_addr = dict(reward_state.rewards_by_address)

        rewards = [0.0] * len(connections)
        for conn in connections:
            if conn.address in rewards_by_addr:
                rewards[conn.player_index] = rewards_by_addr[conn.address]

        stats: EpisodeStats = {
            "game": {"ticks": float(config.max_ticks), "num_players": float(config.num_players)},
            "agent": [dict(action_stats[i]) for i in range(config.num_players)],
        }

        return PureSingleEpisodeResult(
            rewards=rewards,
            action_timeouts=[0] * config.num_players,
            stats=stats,
            steps=config.max_ticks,
        )

    finally:
        reward_state.stop_event.set()
        if reward_state.ws is not None:
            try:
                reward_state.ws.close()
            except Exception:
                pass
        if reward_state.thread is not None:
            reward_state.thread.join(timeout=2.0)

        for loaded_policy in policies:
            close = getattr(loaded_policy.policy, "close", None)
            if close is not None:
                close()

        for conn in connections:
            try:
                conn.ws.close()
            except Exception:
                logger.debug("Failed to close WebSocket for player %d", conn.player_index, exc_info=True)

        if server_proc.poll() is None:
            server_proc.terminate()
            try:
                server_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_proc.kill()
