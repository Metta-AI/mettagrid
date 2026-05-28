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
from typing import Any, Literal

import numpy as np
import websocket

from mettagrid import bitworld_sprite_player
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
    bitworld_input_mask_name,
    pack_chat_packet,
    pack_input_packet,
    parse_reward_packet,
    trim_bitworld_replay_to_first_round,
)
from mettagrid.config.bitworld_config import BitWorldEnvConfig
from mettagrid.policy.policy import MultiAgentPolicy, NimMultiAgentPolicy, PolicySpec
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.runner.types import PureSingleEpisodeJob, PureSingleEpisodeResult
from mettagrid.types import EpisodeStats
from mettagrid.util.uri_resolvers.schemes import parse_uri

logger = logging.getLogger(__name__)

SERVER_START_ATTEMPTS = 5
SERVER_START_GRACE_S = 0.1
SERVER_REPLAY_FLUSH_TIMEOUT_S = 5.0
MAX_FRAME_DRAIN = 128
DEBUG_STATS_ENV = "BITWORLD_DEBUG_STATS"
BitWorldObservationMode = Literal["pixels", "sprite_player"]


class PolicyStepError(Exception):
    pass


@dataclass
class BitWorldRuntime:
    """Runtime settings for the BitWorld server process (not game config)."""

    binary_path: str | None = None
    host: str = "127.0.0.1"
    port: int = 8080


@dataclass
class PlayerConnection:
    ws: websocket.WebSocket
    player_index: int
    address: str
    observation_mode: BitWorldObservationMode = "pixels"
    frame_stack: int = BITWORLD_DEFAULT_FRAME_STACK
    alive: bool = True
    observation_stack: np.ndarray | None = None
    queued_frames: list[bytes] = field(default_factory=list)
    sprite_player_adapter: bitworld_sprite_player.SpritePlayerObservationAdapter | None = None


@dataclass
class RewardState:
    rewards_by_address: dict[str, float] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)
    ws: websocket.WebSocket | None = None
    thread: threading.Thread | None = None
    stop_event: threading.Event = field(default_factory=threading.Event)


def _find_bitworld_binary(game_name: str, binary_path: str | None = None) -> Path:
    if binary_path:
        p = Path(binary_path)
        if p.exists():
            return p
        raise FileNotFoundError(f"BitWorld binary not found: {binary_path}")

    candidates = [
        Path("/opt/bitworld") / game_name / game_name,
        Path.home() / "bitworld" / game_name / game_name,
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(f"BitWorld binary for '{game_name}' not found. Searched: {[str(c) for c in candidates]}")


def _replay_path_from_uri(replay_uri: str | None) -> Path | None:
    if replay_uri is None:
        return None

    parsed = parse_uri(replay_uri, allow_none=False)
    if parsed.scheme != "file":
        raise ValueError(f"BitWorld replay URI must be file://, got: {replay_uri}")
    return parsed.local_path


def _start_server(
    binary_path: Path,
    runtime: BitWorldRuntime,
    env: BitWorldEnvConfig,
    *,
    replay_path: Path | None = None,
) -> subprocess.Popen:
    server_config_fields: dict[str, Any] = {
        **env.server_config,
        "seed": env.seed,
        "maxTicks": env.max_ticks,
        "minPlayers": env.num_players,
    }
    server_config = json.dumps(server_config_fields, separators=(",", ":"))
    cmd = [
        str(binary_path),
        f"--address:{runtime.host}",
        f"--port:{runtime.port}",
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
    runtime: BitWorldRuntime,
    path: str,
    label: str,
    player_name: str | None = None,
    connect_timeout_s: float = 10.0,
) -> websocket.WebSocket:
    url = BitWorldEndpoint(address=runtime.host, port=runtime.port).websocket_url(path, player_name)
    deadline = time.monotonic() + connect_timeout_s
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
    runtime: BitWorldRuntime,
    env: BitWorldEnvConfig,
    *,
    replay_path: Path | None = None,
) -> subprocess.Popen:
    for attempt in range(SERVER_START_ATTEMPTS):
        runtime.port = _pick_free_port()
        server_proc = _start_server(binary_path, runtime, env, replay_path=replay_path)
        time.sleep(SERVER_START_GRACE_S)
        if server_proc.poll() is None:
            return server_proc

        stderr = server_proc.stderr.read().decode(errors="replace").strip() if server_proc.stderr is not None else ""
        logger.warning(
            "BitWorld server exited during startup on port %d (attempt %d/%d): %s",
            runtime.port,
            attempt + 1,
            SERVER_START_ATTEMPTS,
            stderr,
        )

    raise RuntimeError(f"BitWorld server failed to start after {SERVER_START_ATTEMPTS} port attempts")


def _stop_server_after_clients_disconnect(server_proc: subprocess.Popen) -> None:
    deadline = time.monotonic() + SERVER_REPLAY_FLUSH_TIMEOUT_S
    while time.monotonic() < deadline:
        if server_proc.poll() is not None:
            return
        time.sleep(0.05)

    if server_proc.poll() is not None:
        return

    server_proc.terminate()
    terminate_deadline = time.monotonic() + 5.0
    while time.monotonic() < terminate_deadline:
        if server_proc.poll() is not None:
            return
        time.sleep(0.05)

    if server_proc.poll() is None:
        server_proc.kill()


def _build_bitworld_env_interface(
    frame_stack: int = BITWORLD_DEFAULT_FRAME_STACK,
    num_agents: int = 1,
    observation_mode: BitWorldObservationMode = "pixels",
) -> PolicyEnvInterface:
    import gymnasium as gym  # noqa: PLC0415

    if observation_mode == "pixels":
        obs_space = gym.spaces.Box(low=0, high=15, shape=(frame_stack, SCREEN_HEIGHT, SCREEN_WIDTH), dtype=np.uint8)
    elif observation_mode == "sprite_player":
        obs_space = gym.spaces.Box(
            low=0,
            high=255,
            shape=(frame_stack * bitworld_sprite_player.SPRITE_PLAYER_FEATURES,),
            dtype=np.uint8,
        )
    else:
        raise ValueError(f"Unsupported BitWorld observation mode: {observation_mode!r}")
    act_space = gym.spaces.Discrete(BITWORLD_ACTION_COUNT)
    return PolicyEnvInterface.from_spaces(
        observation_space=obs_space,
        action_space=act_space,
        num_agents=num_agents,
        action_names=list(BITWORLD_ACTION_NAMES),
        observation_kind=observation_mode,
    )


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


def _receive_sprite_player_observation(conn: PlayerConnection) -> tuple[np.ndarray | None, int]:
    assert conn.sprite_player_adapter is not None
    adapter = conn.sprite_player_adapter

    if not conn.queued_frames:
        try:
            data = conn.ws.recv()
            if isinstance(data, bytes) and data:
                conn.queued_frames.append(data)
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
                data = conn.ws.recv()
                if isinstance(data, bytes) and data:
                    conn.queued_frames.append(data)
            except (BlockingIOError, websocket.WebSocketTimeoutException):
                break
            except (websocket.WebSocketConnectionClosedException, ConnectionError):
                conn.alive = False
                break
    finally:
        conn.ws.settimeout(previous_timeout)

    if not conn.queued_frames:
        return None, 0

    frame_advance = 0
    for packet in conn.queued_frames:
        if adapter.apply_packet(packet):
            frame_advance += 1
    conn.queued_frames.clear()
    if frame_advance == 0:
        return None, 0
    features = bitworld_sprite_player.SPRITE_PLAYER_FEATURES
    frame = adapter.observation()
    if frame.shape != (features,):
        raise ValueError(f"BitWorld /sprite_player observations must have shape {(features,)}, got {frame.shape}")
    if conn.observation_stack is None:
        conn.observation_stack = np.repeat(frame[np.newaxis, :], conn.frame_stack, axis=0)
    else:
        conn.observation_stack[:-1] = conn.observation_stack[1:]
        conn.observation_stack[-1] = frame
    return conn.observation_stack.reshape(conn.frame_stack * features), frame_advance


def _policy_agent_ids(assignments: list[int], policy_count: int) -> list[list[int]]:
    policy_agent_ids: list[list[int]] = [[] for _ in range(policy_count)]
    for agent_id, policy_index in enumerate(assignments):
        policy_agent_ids[policy_index].append(agent_id)
    return policy_agent_ids


def _load_bitworld_policy(
    uri: str,
    agent_ids: list[int],
    num_agents: int,
    frame_stack: int = BITWORLD_DEFAULT_FRAME_STACK,
) -> MultiAgentPolicy:
    from mettagrid.policy.loader import initialize_or_load_policy  # noqa: PLC0415
    from mettagrid.util.uri_resolvers.schemes import policy_spec_from_uri  # noqa: PLC0415

    policy_spec = PolicySpec(class_path=uri) if "://" not in uri else policy_spec_from_uri(uri)
    if policy_spec.policy_env_interface is None:
        env_interface = _build_bitworld_env_interface(frame_stack, num_agents=num_agents)
    else:
        policy_env_interface = policy_spec.policy_env_interface
        shape = policy_env_interface.observation_shape
        if policy_env_interface.observation_kind == "pixels":
            if len(shape) != 3 or shape[0] < 1 or shape[1:] != (SCREEN_HEIGHT, SCREEN_WIDTH):
                raise ValueError(
                    "BitWorld pixel policies must declare observation shape "
                    f"[frame_stack,{SCREEN_HEIGHT},{SCREEN_WIDTH}], got {shape}"
                )
            env_interface = _build_bitworld_env_interface(shape[0], num_agents=num_agents, observation_mode="pixels")
        elif policy_env_interface.observation_kind == "sprite_player":
            features = bitworld_sprite_player.SPRITE_PLAYER_FEATURES
            if len(shape) != 1 or shape[0] < features or shape[0] % features != 0:
                raise ValueError(
                    "BitWorld sprite_player policies must declare a flat observation shape with "
                    f"{features} features per frame, got {shape}"
                )
            env_interface = _build_bitworld_env_interface(
                shape[0] // features,
                num_agents=num_agents,
                observation_mode="sprite_player",
            )
        else:
            raise ValueError(
                "BitWorld policies must use 'pixels' or 'sprite_player' observations, "
                f"got {policy_env_interface.observation_kind!r}"
            )
    policy = initialize_or_load_policy(env_interface, policy_spec)
    if policy_spec.policy_env_interface is None and isinstance(policy, NimMultiAgentPolicy):
        raise ValueError(
            "BitWorld runner cannot use a synthesized pixel policy_env_interface for native Nim policy "
            f"{policy_spec.class_path!r}; upload the policy with an explicit BitWorld policy_env_interface"
        )
    return policy


def _slot_indexed_observations(observations: np.ndarray, agent_ids: list[int], num_agents: int) -> np.ndarray:
    slot_observations = np.zeros((num_agents, *observations.shape[1:]), dtype=observations.dtype)
    slot_observations[np.asarray(agent_ids, dtype=np.intp)] = observations
    return slot_observations


def _policy_step_actions(
    policy: MultiAgentPolicy,
    observations: np.ndarray,
    actions: np.ndarray,
    agent_ids: list[int],
    num_agents: int,
) -> None:
    slot_actions = np.zeros((num_agents,), dtype=actions.dtype)
    policy.step_batch(_slot_indexed_observations(observations, agent_ids, num_agents), slot_actions)
    actions[:] = slot_actions[np.asarray(agent_ids, dtype=np.intp)]


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
    num_agents: int | None = None,
) -> tuple[np.ndarray, list[str | None], list[dict[str, float]]]:
    num_agents = max(agent_ids) + 1 if num_agents is None else num_agents
    actions = np.zeros((observations.shape[0],), dtype=np.int64)
    _policy_step_actions(policy, observations, actions, agent_ids, num_agents)
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


def _action_stat_key(action_mask: int) -> str:
    return f"action.{bitworld_input_mask_name(action_mask)}.success"


def run_bitworld_episode(job: PureSingleEpisodeJob) -> PureSingleEpisodeResult:
    if not isinstance(job.env, BitWorldEnvConfig):
        raise TypeError(f"Expected BitWorldEnvConfig for bitworld episode, got {type(job.env).__name__}")

    env = job.env.model_copy(update={"seed": job.seed})
    game_name = env.game_name
    num_players = env.num_players
    max_ticks = env.max_ticks
    frame_stack = BITWORLD_DEFAULT_FRAME_STACK

    if len(job.assignments) != num_players:
        raise ValueError(f"BitWorld {game_name} expects {num_players} assignments, got {len(job.assignments)}")

    policies: list[MultiAgentPolicy] = []
    policy_agent_ids = _policy_agent_ids(job.assignments, len(job.policy_uris))
    for policy_index, uri in enumerate(job.policy_uris):
        policies.append(_load_bitworld_policy(uri, policy_agent_ids[policy_index], num_players, frame_stack))

    runtime = BitWorldRuntime()
    binary_path = _find_bitworld_binary(game_name)
    client_data_dir = binary_path.parents[1] / "client" / "data"
    replay_path = _replay_path_from_uri(job.replay_uri)
    server_proc = _start_server_on_free_port(binary_path, runtime, env, replay_path=replay_path)

    connections: list[PlayerConnection] = []
    reward_state = RewardState()
    action_stats: list[defaultdict[str, float]] = [defaultdict(float) for _ in range(num_players)]

    try:
        timeout_s = env.connect_timeout_s
        reward_state.ws = _connect_websocket(runtime, REWARD_PATH, "reward listener", connect_timeout_s=timeout_s)
        reward_state.thread = threading.Thread(target=_reward_listener, args=(reward_state,), daemon=True)
        reward_state.thread.start()

        for i in range(num_players):
            address = f"player_{i}"
            policy = policies[job.assignments[i]]
            policy_env_info = policy.policy_env_info
            shape = policy_env_info.observation_shape
            if policy_env_info.observation_kind == "pixels":
                observation_mode: BitWorldObservationMode = "pixels"
                connection_frame_stack = shape[0]
            elif policy_env_info.observation_kind == "sprite_player":
                observation_mode = "sprite_player"
                connection_frame_stack = shape[0] // bitworld_sprite_player.SPRITE_PLAYER_FEATURES
            else:
                raise ValueError(
                    "BitWorld policies must use 'pixels' or 'sprite_player' observations, "
                    f"got {policy_env_info.observation_kind!r}"
                )
            path = bitworld_sprite_player.SPRITE_PLAYER_PATH if observation_mode == "sprite_player" else PLAYER_PATH
            ws = _connect_websocket(runtime, path, f"player {i}", player_name=address, connect_timeout_s=timeout_s)
            connections.append(
                PlayerConnection(
                    ws=ws,
                    player_index=i,
                    address=address,
                    observation_mode=observation_mode,
                    frame_stack=connection_frame_stack,
                    sprite_player_adapter=(
                        bitworld_sprite_player.SpritePlayerObservationAdapter(client_data_dir)
                        if observation_mode == "sprite_player"
                        else None
                    ),
                )
            )

        for _tick in range(max_ticks):
            all_dead = True
            pending_actions: list[tuple[PlayerConnection, MultiAgentPolicy, np.ndarray, int]] = []
            for conn in connections:
                if not conn.alive:
                    continue
                all_dead = False

                if conn.observation_mode == "sprite_player":
                    observation, frame_advance = _receive_sprite_player_observation(conn)
                else:
                    frame_data, frame_advance = _receive_player_frame(conn)
                    observation = None if frame_data is None else _stack_observation(conn, frame_data, conn.frame_stack)
                if observation is None:
                    continue

                policy = policies[job.assignments[conn.player_index]]
                pending_actions.append((conn, policy, observation, frame_advance))

            for policy in policies:
                batch = [
                    (conn, observation, frame_advance)
                    for conn, policy_for_conn, observation, frame_advance in pending_actions
                    if policy_for_conn is policy
                ]
                if not batch:
                    continue
                observations = np.stack([observation for _conn, observation, _frame_advance in batch])
                agent_ids = [conn.player_index for conn, _observation, _frame_advance in batch]
                action_masks, chat_messages, debug_stats = _policy_action_masks_and_chats(
                    policy, observations, agent_ids, num_players
                )
                for (conn, _observation, frame_advance), action_mask, chat_message, debug_stat in zip(
                    batch,
                    action_masks,
                    chat_messages,
                    debug_stats,
                    strict=True,
                ):
                    mask = int(action_mask)
                    input_packet = (
                        bitworld_sprite_player.pack_sprite_player_input_packet(mask & 0x7F)
                        if conn.observation_mode == "sprite_player"
                        else pack_input_packet(mask)
                    )
                    conn.ws.send(input_packet, websocket.ABNF.OPCODE_BINARY)
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
                        chat_packet = (
                            bitworld_sprite_player.pack_sprite_player_chat_packet(chat_message)
                            if conn.observation_mode == "sprite_player"
                            else pack_chat_packet(chat_message)
                        )
                        conn.ws.send(chat_packet, websocket.ABNF.OPCODE_BINARY)
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
            "game": {"ticks": float(max_ticks), "num_players": float(num_players)},
            "agent": [dict(action_stats[i]) for i in range(num_players)],
        }

        result = PureSingleEpisodeResult(
            rewards=rewards,
            action_timeouts=[0] * num_players,
            stats=stats,
            steps=max_ticks,
            overage_exceeded_at=[None] * num_players,
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

        for policy in policies:
            close = getattr(policy, "close", None)
            if close is not None:
                close()

        for conn in connections:
            try:
                conn.ws.close()
            except Exception:
                logger.debug("Failed to close WebSocket for player %d", conn.player_index, exc_info=True)

        _stop_server_after_clients_disconnect(server_proc)

    if replay_path is not None and trim_bitworld_replay_to_first_round(replay_path):
        logger.warning("Trimmed BitWorld replay after tick hash reset: %s", replay_path)

    return result
