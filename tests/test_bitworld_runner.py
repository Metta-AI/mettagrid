import io
import json
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest
import torch
from safetensors.torch import save_file

from mettagrid.policy.policy import PolicySpec
from mettagrid.runner import bitworld_runner


def test_find_bitworld_binary_uses_container_layout(monkeypatch):
    expected = Path("/opt/bitworld/among_them/among_them")
    monkeypatch.setattr(Path, "exists", lambda path: path == expected)

    assert bitworld_runner._find_bitworld_binary(bitworld_runner.BitWorldConfig()) == expected


class _FakeProc:
    def __init__(self, alive: bool):
        self._alive = alive
        self.stderr = io.BytesIO(b"address already in use")

    def poll(self) -> int | None:
        return None if self._alive else 1


def test_start_server_on_free_port_retries_after_failed_bind(monkeypatch):
    ports = iter([1001, 1002])
    started_ports: list[int] = []

    monkeypatch.setattr(bitworld_runner, "_pick_free_port", lambda: next(ports))
    monkeypatch.setattr(bitworld_runner.time, "sleep", lambda _seconds: None)

    def fake_start_server(_binary_path: Path, config: bitworld_runner.BitWorldConfig) -> _FakeProc:
        started_ports.append(config.port)
        return _FakeProc(alive=len(started_ports) == 2)

    monkeypatch.setattr(bitworld_runner, "_start_server", fake_start_server)

    config = bitworld_runner.BitWorldConfig()
    server_proc = bitworld_runner._start_server_on_free_port(Path("/tmp/bitworld"), config)

    assert server_proc.poll() is None
    assert started_ports == [1001, 1002]
    assert config.port == 1002


def test_config_requires_current_among_them_agent_count():
    with pytest.raises(ValueError, match="expects 5 agents"):
        bitworld_runner.BitWorldConfig.from_env_config({"game": {"max_steps": 99, "num_agents": 1}})


def test_start_server_uses_among_them_multi_player_config(monkeypatch):
    captured: dict[str, object] = {}

    def fake_popen(cmd, cwd, stdout, stderr):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["stdout"] = stdout
        captured["stderr"] = stderr
        return _FakeProc(alive=True)

    monkeypatch.setattr(bitworld_runner.subprocess, "Popen", fake_popen)

    config = bitworld_runner.BitWorldConfig(host="0.0.0.0", port=8123, seed=17, max_ticks=99)
    server_proc = bitworld_runner._start_server(Path("/tmp/bitworld/among_them"), config)

    cmd = cast(list[str], captured["cmd"])
    assert server_proc.poll() is None
    assert cmd[:3] == ["/tmp/bitworld/among_them", "--address:0.0.0.0", "--port:8123"]
    assert json.loads(cmd[3].removeprefix("--config:")) == {"seed": 17, "maxTicks": 99, "minPlayers": 5}
    assert captured["cwd"] == "/tmp/bitworld"


class _FakeWebSocket:
    urls: list[str] = []

    def settimeout(self, _timeout: float) -> None:
        pass

    def connect(self, url: str) -> None:
        self.urls.append(url)


def test_connect_websocket_uses_named_among_them_player_url(monkeypatch):
    _FakeWebSocket.urls = []
    monkeypatch.setattr(bitworld_runner.websocket, "WebSocket", _FakeWebSocket)

    bitworld_runner._connect_websocket(
        bitworld_runner.BitWorldConfig(port=8123),
        bitworld_runner.PLAYER_PATH,
        "player 2",
        player_name="player_2",
    )

    assert _FakeWebSocket.urls == ["ws://127.0.0.1:8123/player?name=player_2"]


def test_bitworld_env_interface_uses_trainable_action_space():
    env_interface = bitworld_runner._build_bitworld_env_interface()

    assert env_interface.observation_space.shape == (
        bitworld_runner.BITWORLD_DEFAULT_FRAME_STACK,
        bitworld_runner.SCREEN_HEIGHT,
        bitworld_runner.SCREEN_WIDTH,
    )
    assert env_interface.observation_space.dtype == np.uint8
    assert env_interface.observation_kind == "pixels"
    assert list(env_interface.action_names) == list(bitworld_runner.BITWORLD_ACTION_NAMES)
    assert env_interface.action_names[0] == "noop"
    assert env_interface.action_names[1] == "a"
    assert len(env_interface.action_names) == 27


def test_bitworld_env_interface_accepts_checkpoint_frame_stack():
    env_interface = bitworld_runner._build_bitworld_env_interface(frame_stack=2)

    assert env_interface.observation_space.shape == (2, bitworld_runner.SCREEN_HEIGHT, bitworld_runner.SCREEN_WIDTH)


def test_unpack_frame_expands_4bit_palette_indices():
    packed = bytes([0x21, 0xF0]) + bytes(bitworld_runner.PROTOCOL_BYTES - 2)

    frame = bitworld_runner.unpack_frame(packed)

    assert frame.shape == (bitworld_runner.SCREEN_HEIGHT, bitworld_runner.SCREEN_WIDTH)
    assert frame.dtype == np.uint8
    assert frame[0, :4].tolist() == [1, 2, 0, 15]


def test_unpack_frame_rejects_wrong_size():
    with pytest.raises(ValueError, match="BitWorld frames"):
        bitworld_runner.unpack_frame(b"\x00")


def test_infer_policy_frame_stack_from_checkpoint_weights(tmp_path):
    weights_path = tmp_path / "weights.safetensors"
    save_file(
        {"_sequential_network.module.feature_extractor.func.extractor.cnn1.weight": torch.zeros((64, 3, 3, 3))},
        weights_path,
    )
    policy_spec = PolicySpec(class_path="metta.agent.policy.CheckpointPolicy", data_path=str(weights_path))

    assert bitworld_runner._infer_policy_frame_stack(policy_spec) == 3


def test_stack_observation_unpacks_server_frames_and_preserves_history():
    conn = bitworld_runner.PlayerConnection(ws=cast(Any, _FakeWebSocket()), player_index=0, address="player_0")
    first = (np.arange(bitworld_runner.FRAME_PIXELS, dtype=np.uint8) % 16).reshape(
        bitworld_runner.SCREEN_HEIGHT, bitworld_runner.SCREEN_WIDTH
    )
    second = np.full((bitworld_runner.SCREEN_HEIGHT, bitworld_runner.SCREEN_WIDTH), 7, dtype=np.uint8)

    first_obs = bitworld_runner._stack_observation(conn, _pack_frame(first), frame_stack=2)
    assert first_obs.shape == (2, bitworld_runner.SCREEN_HEIGHT, bitworld_runner.SCREEN_WIDTH)
    assert np.array_equal(first_obs[0], first)
    assert np.array_equal(first_obs[1], first)

    second_obs = bitworld_runner._stack_observation(conn, _pack_frame(second), frame_stack=2)
    assert np.array_equal(second_obs[0], first)
    assert np.array_equal(second_obs[1], second)


def _pack_frame(frame: np.ndarray) -> bytes:
    flat = frame.reshape(-1)
    return bytes((flat[0::2] | (flat[1::2] << 4)).tolist())
