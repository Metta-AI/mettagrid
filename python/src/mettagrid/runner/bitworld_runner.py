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
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import websocket

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
    pack_input_packet,
    parse_reward_packet,
    unpack_frame_pixels,
)
from mettagrid.policy.policy import MultiAgentPolicy, PolicySpec
from mettagrid.runner.types import PureSingleEpisodeJob, PureSingleEpisodeResult
from mettagrid.types import EpisodeStats

logger = logging.getLogger(__name__)

SERVER_START_ATTEMPTS = 5
SERVER_START_GRACE_S = 0.1
BITWORLD_CNN_INPUT_WEIGHT_SUFFIX = "feature_extractor.func.extractor.cnn1.weight"

BITWORLD_AMONG_THEM_AGENT_COUNT = 5
BITWORLD_GAME_NAME = "among_them"


@dataclass
class BitWorldConfig:
    binary_path: str | None = None
    host: str = "127.0.0.1"
    port: int = 8080
    seed: int = 0
    max_ticks: int = 10000
    num_players: int = BITWORLD_AMONG_THEM_AGENT_COUNT
    connect_timeout_s: float = 10.0

    @classmethod
    def from_env_config(cls, config: dict[str, Any]) -> BitWorldConfig:
        game = config["game"]
        num_players = game["num_agents"]
        if num_players != BITWORLD_AMONG_THEM_AGENT_COUNT:
            raise ValueError(
                f"BitWorld {BITWORLD_GAME_NAME} expects {BITWORLD_AMONG_THEM_AGENT_COUNT} agents, got {num_players}"
            )
        return cls(
            max_ticks=game["max_steps"],
            num_players=num_players,
        )


@dataclass
class PlayerConnection:
    ws: websocket.WebSocket
    player_index: int
    address: str
    alive: bool = True
    observation_stack: np.ndarray | None = None


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


def _start_server(binary_path: Path, config: BitWorldConfig) -> subprocess.Popen:
    server_config = json.dumps(
        {
            "seed": config.seed,
            "maxTicks": config.max_ticks,
            "minPlayers": config.num_players,
        },
        separators=(",", ":"),
    )
    cmd = [
        str(binary_path),
        f"--address:{config.host}",
        f"--port:{config.port}",
        f"--config:{server_config}",
    ]
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


def _start_server_on_free_port(binary_path: Path, config: BitWorldConfig) -> subprocess.Popen:
    for attempt in range(SERVER_START_ATTEMPTS):
        config.port = _pick_free_port()
        server_proc = _start_server(binary_path, config)
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


def _build_bitworld_env_interface(frame_stack: int = BITWORLD_DEFAULT_FRAME_STACK) -> Any:
    import gymnasium as gym  # noqa: PLC0415

    from mettagrid.policy.policy_env_interface import PolicyEnvInterface  # noqa: PLC0415

    obs_space = gym.spaces.Box(low=0, high=15, shape=(frame_stack, SCREEN_HEIGHT, SCREEN_WIDTH), dtype=np.uint8)
    act_space = gym.spaces.Discrete(BITWORLD_ACTION_COUNT)
    return PolicyEnvInterface.from_spaces(
        observation_space=obs_space,
        action_space=act_space,
        num_agents=1,
        action_names=list(BITWORLD_ACTION_NAMES),
        observation_kind="palette_screen",
    )


def _infer_policy_frame_stack(policy_spec: PolicySpec) -> int:
    if not policy_spec.data_path:
        return BITWORLD_DEFAULT_FRAME_STACK

    weights_path = Path(policy_spec.data_path)
    if weights_path.suffix != ".safetensors":
        return BITWORLD_DEFAULT_FRAME_STACK

    from safetensors import safe_open  # noqa: PLC0415

    with safe_open(weights_path, framework="pt", device="cpu") as weights:
        input_weight_keys = [key for key in weights.keys() if key.endswith(BITWORLD_CNN_INPUT_WEIGHT_SUFFIX)]
        if len(input_weight_keys) != 1:
            raise ValueError(
                f"Expected one BitWorld CNN input weight in {weights_path}, found {len(input_weight_keys)}"
            )
        shape = weights.get_tensor(input_weight_keys[0]).shape

    frame_stack = int(shape[1])
    if frame_stack < 1:
        raise ValueError(f"BitWorld frame stack must be positive, got {frame_stack}")
    return frame_stack


def _unpack_frame(frame_data: bytes) -> np.ndarray:
    frame = np.frombuffer(unpack_frame_pixels(frame_data), dtype=np.uint8)
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


def _policy_action_masks(policy: MultiAgentPolicy, observations: np.ndarray) -> np.ndarray:
    actions = np.zeros((observations.shape[0],), dtype=np.int64)
    policy.step_batch(observations, actions)
    invalid_indices = np.flatnonzero((actions < 0) | (actions >= BITWORLD_ACTION_COUNT))
    if invalid_indices.size:
        batch_index = int(invalid_indices[0])
        raise ValueError(
            f"BitWorld policy action index must be in [0, {BITWORLD_ACTION_COUNT}), "
            f"got {int(actions[batch_index])} at batch index {batch_index}"
        )
    return BITWORLD_ACTION_MASKS[actions]


def run_bitworld_episode(job: PureSingleEpisodeJob) -> PureSingleEpisodeResult:
    from mettagrid.policy.loader import initialize_or_load_policy  # noqa: PLC0415
    from mettagrid.util.uri_resolvers.schemes import policy_spec_from_uri  # noqa: PLC0415

    config = BitWorldConfig.from_env_config(job.env.model_dump(mode="json"))
    config.seed = job.seed
    if len(job.assignments) != config.num_players:
        raise ValueError(
            f"BitWorld {BITWORLD_GAME_NAME} expects {config.num_players} assignments, got {len(job.assignments)}"
        )

    policies: list[LoadedBitWorldPolicy] = []
    for uri in job.policy_uris:
        policy_spec = PolicySpec(class_path=uri) if "://" not in uri else policy_spec_from_uri(uri)
        frame_stack = _infer_policy_frame_stack(policy_spec)
        env_interface = _build_bitworld_env_interface(frame_stack)
        policies.append(LoadedBitWorldPolicy(initialize_or_load_policy(env_interface, policy_spec), frame_stack))

    binary_path = _find_bitworld_binary(config)
    server_proc = _start_server_on_free_port(binary_path, config)

    connections: list[PlayerConnection] = []
    reward_state = RewardState()

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
            pending_actions: list[tuple[PlayerConnection, LoadedBitWorldPolicy, np.ndarray]] = []
            for conn in connections:
                if not conn.alive:
                    continue
                all_dead = False

                try:
                    frame_data = conn.ws.recv()
                except websocket.WebSocketTimeoutException:
                    continue
                except (websocket.WebSocketConnectionClosedException, ConnectionError):
                    conn.alive = False
                    continue

                if not isinstance(frame_data, bytes) or len(frame_data) != PROTOCOL_BYTES:
                    continue

                loaded_policy = policies[job.assignments[conn.player_index]]
                observation = _stack_observation(conn, frame_data, loaded_policy.frame_stack)
                pending_actions.append((conn, loaded_policy, observation))

            for loaded_policy in policies:
                batch = [
                    (conn, observation)
                    for conn, policy_for_conn, observation in pending_actions
                    if policy_for_conn is loaded_policy
                ]
                if not batch:
                    continue
                observations = np.stack([observation for _conn, observation in batch])
                action_masks = _policy_action_masks(loaded_policy.policy, observations)
                for (conn, _observation), action_mask in zip(batch, action_masks, strict=True):
                    conn.ws.send(pack_input_packet(int(action_mask)), websocket.ABNF.OPCODE_BINARY)

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
            "agent": [{"reward": rewards[i]} for i in range(config.num_players)],
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
