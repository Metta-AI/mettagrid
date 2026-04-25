"""BitWorld game engine runner.

Runs a BitWorld game server as a subprocess and connects policies via WebSocket.
BitWorld protocol: 128x128 pixel frames (8192 bytes packed, 4 bits/pixel, 16-color palette),
1-byte action bitmasks (up/down/left/right/select/A/B).
"""

from __future__ import annotations

import logging
import socket
import struct
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import websocket

from mettagrid.runner.types import PureSingleEpisodeJob, PureSingleEpisodeResult
from mettagrid.types import EpisodeStats

logger = logging.getLogger(__name__)

SCREEN_WIDTH = 128
SCREEN_HEIGHT = 128
PROTOCOL_BYTES = (SCREEN_WIDTH * SCREEN_HEIGHT) // 2
SERVER_START_ATTEMPTS = 5
SERVER_START_GRACE_S = 0.1

BUTTON_UP = 1 << 0
BUTTON_DOWN = 1 << 1
BUTTON_LEFT = 1 << 2
BUTTON_RIGHT = 1 << 3
BUTTON_A = 1 << 5

_DEBUG_ACTIONS = [
    BUTTON_LEFT,
    BUTTON_RIGHT,
    BUTTON_UP,
    BUTTON_DOWN,
    BUTTON_A,
]


@dataclass
class BitWorldConfig:
    game_name: str = "among_them"
    binary_path: str | None = None
    host: str = "127.0.0.1"
    port: int = 8080
    max_ticks: int = 10000
    connect_timeout_s: float = 10.0

    @classmethod
    def from_env_config(cls, config: dict[str, Any]) -> BitWorldConfig:
        game = config.get("game", {})
        label = config.get("label", "")
        game_name = label.removeprefix("bitworld_") if label.startswith("bitworld_") else "among_them"
        return cls(
            game_name=game_name,
            max_ticks=game.get("max_steps", 10000),
        )


@dataclass
class PlayerConnection:
    ws: websocket.WebSocket
    player_index: int
    alive: bool = True


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


def _start_server(binary_path: Path, config: BitWorldConfig) -> subprocess.Popen:
    # Nim parseopt uses --key=value syntax, not --key value
    cmd = [
        str(binary_path),
        f"--address={config.host}",
        f"--port={config.port}",
    ]
    logger.info("Starting BitWorld server: %s", " ".join(cmd))
    return subprocess.Popen(
        cmd,
        cwd=str(binary_path.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _connect_player(config: BitWorldConfig, player_index: int) -> websocket.WebSocket:
    url = f"ws://{config.host}:{config.port}/ws"
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


def _pick_free_port() -> int:
    # The caller retries server startup if this freed port is claimed before bind.
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


def run_bitworld_episode(job: PureSingleEpisodeJob) -> PureSingleEpisodeResult:
    config = BitWorldConfig.from_env_config(job.env.model_dump(mode="json"))
    binary_path = _find_bitworld_binary(config)
    server_proc = _start_server_on_free_port(binary_path, config)

    connections: list[PlayerConnection] = []
    num_agents = len(job.assignments)

    try:
        for i in range(num_agents):
            ws = _connect_player(config, i)
            connections.append(
                PlayerConnection(
                    ws=ws,
                    player_index=i,
                )
            )

        rewards = [0.0] * num_agents

        # TODO: BitWorld server should support max_ticks natively and auto-terminate;
        # until then the runner enforces the tick limit client-side.
        for _tick in range(config.max_ticks):
            for conn in connections:
                if not conn.alive:
                    continue

                try:
                    frame_data = conn.ws.recv()
                except websocket.WebSocketTimeoutException:
                    continue
                except (websocket.WebSocketConnectionClosedException, ConnectionError):
                    conn.alive = False
                    continue

                if not isinstance(frame_data, bytes) or len(frame_data) != PROTOCOL_BYTES:
                    continue

                action = _DEBUG_ACTIONS[conn.player_index % len(_DEBUG_ACTIONS)]
                conn.ws.send(struct.pack("B", action), websocket.ABNF.OPCODE_BINARY)

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
