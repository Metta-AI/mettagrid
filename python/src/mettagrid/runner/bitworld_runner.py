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
import struct
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import websocket

from mettagrid.runner.types import PureSingleEpisodeJob, PureSingleEpisodeResult
from mettagrid.types import EpisodeStats

logger = logging.getLogger(__name__)

SCREEN_WIDTH = 128
SCREEN_HEIGHT = 128
PROTOCOL_BYTES = (SCREEN_WIDTH * SCREEN_HEIGHT) // 2
SERVER_START_ATTEMPTS = 5
SERVER_START_GRACE_S = 0.1
BITWORLD_ACTION_COUNT = 128


@dataclass
class BitWorldConfig:
    game_name: str = "among_them"
    binary_path: str | None = None
    host: str = "127.0.0.1"
    port: int = 8080
    max_ticks: int = 10000
    num_players: int = 5
    connect_timeout_s: float = 10.0

    @classmethod
    def from_env_config(cls, config: dict[str, Any]) -> BitWorldConfig:
        game = config.get("game", {})
        label = config.get("label", "")
        game_name = label.removeprefix("bitworld_") if label.startswith("bitworld_") else "among_them"
        return cls(
            game_name=game_name,
            max_ticks=game.get("max_steps", 10000),
            num_players=game.get("num_agents", 5),
        )


@dataclass
class PlayerConnection:
    ws: websocket.WebSocket
    player_index: int
    address: str
    alive: bool = True
    latest_frame: bytes | None = None


@dataclass
class RewardState:
    """Tracks accumulated rewards from the /reward WebSocket."""

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
        Path("/opt/bitworld") / config.game_name / config.game_name,
        Path.home() / "bitworld" / config.game_name / config.game_name,
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        f"BitWorld binary for '{config.game_name}' not found. Searched: {[str(c) for c in candidates]}"
    )


def _build_server_config_json(config: BitWorldConfig) -> str:
    """Build JSON config string to pass to the BitWorld server."""
    return json.dumps(
        {
            "minPlayers": config.num_players,
            "maxTicks": config.max_ticks,
        }
    )


def _start_server(binary_path: Path, config: BitWorldConfig) -> subprocess.Popen:
    config_json = _build_server_config_json(config)
    cmd = [
        str(binary_path),
        f"--address={config.host}",
        f"--port={config.port}",
        f"--config={config_json}",
    ]
    logger.info("Starting BitWorld server: %s", " ".join(cmd))
    return subprocess.Popen(
        cmd,
        cwd=str(binary_path.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _connect_player(config: BitWorldConfig, player_index: int) -> websocket.WebSocket:
    url = f"ws://{config.host}:{config.port}/player?name=player_{player_index}"
    deadline = time.monotonic() + config.connect_timeout_s
    last_error = None
    while time.monotonic() < deadline:
        ws = websocket.WebSocket()
        ws.settimeout(2.0)
        try:
            ws.connect(url)
            logger.info("Connected player %d to %s", player_index, url)
            return ws
        except (ConnectionRefusedError, OSError, websocket.WebSocketException) as e:
            last_error = e
            time.sleep(0.1)
    raise ConnectionError(f"Could not connect to BitWorld server at {url}: {last_error}")


def _connect_reward_ws(config: BitWorldConfig) -> websocket.WebSocket:
    url = f"ws://{config.host}:{config.port}/reward"
    deadline = time.monotonic() + config.connect_timeout_s
    last_error = None
    while time.monotonic() < deadline:
        ws = websocket.WebSocket()
        ws.settimeout(2.0)
        try:
            ws.connect(url)
            logger.info("Connected reward listener to %s", url)
            return ws
        except (ConnectionRefusedError, OSError, websocket.WebSocketException) as e:
            last_error = e
            time.sleep(0.1)
    raise ConnectionError(f"Could not connect to BitWorld reward endpoint at {url}: {last_error}")


def _reward_listener(state: RewardState) -> None:
    """Background thread that reads reward messages from the /reward WebSocket."""
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
        for line in data.strip().split("\n"):
            parts = line.split()
            if len(parts) == 3 and parts[0] == "reward":
                address = parts[1]
                try:
                    reward = float(parts[2])
                except ValueError:
                    continue
                with state.lock:
                    state.rewards_by_address[address] = reward


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


def _build_bitworld_env_interface() -> Any:
    """Build a PolicyEnvInterface for BitWorld's observation/action spaces."""
    import gymnasium as gym  # noqa: PLC0415

    from mettagrid.policy.policy_env_interface import PolicyEnvInterface  # noqa: PLC0415

    def _action_names() -> list[str]:
        names = []
        buttons = ("up", "down", "left", "right", "select", "a", "b")
        for mask in range(128):
            pressed = [b for i, b in enumerate(buttons) if mask & (1 << i)]
            names.append("+".join(pressed) if pressed else "noop")
        return names

    obs_space = gym.spaces.Box(low=0, high=255, shape=(PROTOCOL_BYTES,), dtype=np.uint8)
    act_space = gym.spaces.Discrete(BITWORLD_ACTION_COUNT)
    return PolicyEnvInterface.from_spaces(
        observation_space=obs_space,
        action_space=act_space,
        num_agents=1,
        action_names=_action_names(),
        observation_kind="bitworld",
    )


def run_bitworld_episode(job: PureSingleEpisodeJob) -> PureSingleEpisodeResult:
    config = BitWorldConfig.from_env_config(job.env.model_dump(mode="json"))
    binary_path = _find_bitworld_binary(config)
    server_proc = _start_server_on_free_port(binary_path, config)

    connections: list[PlayerConnection] = []
    num_agents = len(job.assignments)
    reward_state = RewardState()

    try:
        # Connect all players. The server stays in Lobby phase until
        # minPlayers (== num_agents) have connected, then auto-starts.
        for i in range(num_agents):
            ws = _connect_player(config, i)
            connections.append(
                PlayerConnection(
                    ws=ws,
                    player_index=i,
                    address=f"player_{i}",
                )
            )

        # Connect reward listener
        reward_state.ws = _connect_reward_ws(config)
        reward_state.thread = threading.Thread(target=_reward_listener, args=(reward_state,), daemon=True)
        reward_state.thread.start()

        # Load policies
        env_interface = _build_bitworld_env_interface()
        from mettagrid.policy.loader import initialize_or_load_policy  # noqa: PLC0415
        from mettagrid.policy.policy import PolicySpec  # noqa: PLC0415
        from mettagrid.util.uri_resolvers.schemes import policy_spec_from_uri  # noqa: PLC0415

        def _resolve_policy_spec(uri: str) -> PolicySpec:
            # Raw class paths (from run_episode_local) don't have a scheme
            if "://" not in uri:
                return PolicySpec(class_path=uri)
            return policy_spec_from_uri(uri)

        policy_specs = [_resolve_policy_spec(uri) for uri in job.policy_uris]
        policies = [initialize_or_load_policy(env_interface, spec) for spec in policy_specs]

        # Run the episode tick loop
        for _tick in range(config.max_ticks):
            all_dead = True
            for conn in connections:
                if not conn.alive:
                    continue
                all_dead = False

                # Receive frame
                try:
                    frame_data = conn.ws.recv()
                except websocket.WebSocketTimeoutException:
                    continue
                except (websocket.WebSocketConnectionClosedException, ConnectionError):
                    conn.alive = False
                    continue

                if not isinstance(frame_data, bytes) or len(frame_data) != PROTOCOL_BYTES:
                    continue

                conn.latest_frame = frame_data

                # Get action from policy
                policy_index = job.assignments[conn.player_index]
                policy = policies[policy_index]
                obs = np.frombuffer(frame_data, dtype=np.uint8)
                actions = np.zeros((1,), dtype=np.int64)
                policy.step_batch(obs.reshape(1, -1), actions)
                action_mask = int(actions[0]) % BITWORLD_ACTION_COUNT

                # Send action to server
                conn.ws.send(struct.pack("B", action_mask), websocket.ABNF.OPCODE_BINARY)

            if all_dead:
                break

        # Collect final rewards from the reward listener
        with reward_state.lock:
            rewards_by_addr = dict(reward_state.rewards_by_address)

        # Map rewards to agent indices. The server uses addresses like "player_0", etc.
        # but the actual address depends on how the server assigns them. We use the
        # connection order as a fallback.
        rewards = [0.0] * num_agents
        for conn in connections:
            if conn.address in rewards_by_addr:
                rewards[conn.player_index] = rewards_by_addr[conn.address]

        # If no address-based rewards were found, try positional mapping
        if all(r == 0.0 for r in rewards) and rewards_by_addr:
            sorted_addrs = sorted(rewards_by_addr.keys())
            for i, addr in enumerate(sorted_addrs):
                if i < num_agents:
                    rewards[i] = rewards_by_addr[addr]

        stats: EpisodeStats = {
            "game": {"ticks": float(config.max_ticks), "num_players": float(num_agents)},
            "agent": [{"reward": rewards[i]} for i in range(num_agents)],
        }

        return PureSingleEpisodeResult(
            rewards=rewards,
            action_timeouts=[0] * num_agents,
            stats=stats,
            steps=config.max_ticks,
        )

    finally:
        # Stop reward listener
        reward_state.stop_event.set()
        if reward_state.ws is not None:
            try:
                reward_state.ws.close()
            except Exception:
                pass
        if reward_state.thread is not None:
            reward_state.thread.join(timeout=2.0)

        # Close player connections
        for conn in connections:
            try:
                conn.ws.close()
            except Exception:
                logger.debug("Failed to close WebSocket for player %d", conn.player_index, exc_info=True)

        # Shut down server
        if server_proc.poll() is None:
            server_proc.terminate()
            try:
                server_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_proc.kill()
