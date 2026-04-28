import io
import json
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest

from mettagrid import MettaGridConfig
from mettagrid.bitworld import BitWorldServerConfig
from mettagrid.policy.policy import PolicySpec
from mettagrid.runner import bitworld_runner
from mettagrid.runner.types import PureSingleEpisodeJob


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

    def terminate(self) -> None:
        self._alive = False

    def wait(self, timeout: float | None = None) -> None:
        del timeout
        self._alive = False

    def kill(self) -> None:
        self._alive = False


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


def test_config_uses_env_agent_and_imposter_count():
    config = bitworld_runner.BitWorldConfig.from_env_config(
        {"game": {"max_steps": 99, "num_agents": 8, "bitworld": {"imposterCount": 2}}}
    )

    assert config.max_ticks == 99
    assert config.num_players == 8
    assert config.imposter_count == 2


def test_config_defaults_to_one_imposter():
    config = bitworld_runner.BitWorldConfig.from_env_config({"game": {"max_steps": 99, "num_agents": 8}})

    assert config.imposter_count == 1


def test_episode_job_validation_preserves_bitworld_config():
    env = MettaGridConfig.EmptyRoom(num_agents=8)
    env.game.max_steps = 99
    env.game.bitworld = BitWorldServerConfig(imposter_count=2)

    job = PureSingleEpisodeJob.model_validate(
        {
            "policy_uris": ["mock://policy"],
            "assignments": [0] * 8,
            "env": env.model_dump(mode="json"),
            "game_engine": "bitworld",
            "results_uri": None,
            "replay_uri": None,
        }
    )
    config = bitworld_runner.BitWorldConfig.from_env_config(job.env.model_dump(mode="json"))

    assert config.max_ticks == 99
    assert config.num_players == 8
    assert config.imposter_count == 2


def test_config_rejects_empty_among_them_agent_count():
    with pytest.raises(ValueError, match="greater than or equal to 1"):
        bitworld_runner.BitWorldConfig.from_env_config({"game": {"max_steps": 99, "num_agents": 0}})


def test_start_server_uses_among_them_multi_player_config(monkeypatch):
    captured: dict[str, object] = {}

    def fake_popen(cmd, cwd, stdout, stderr):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["stdout"] = stdout
        captured["stderr"] = stderr
        return _FakeProc(alive=True)

    monkeypatch.setattr(bitworld_runner.subprocess, "Popen", fake_popen)

    config = bitworld_runner.BitWorldConfig(
        host="0.0.0.0", port=8123, seed=17, max_ticks=99, num_players=8, imposter_count=2
    )
    server_proc = bitworld_runner._start_server(Path("/tmp/bitworld/among_them"), config)

    cmd = cast(list[str], captured["cmd"])
    assert server_proc.poll() is None
    assert cmd[:3] == ["/tmp/bitworld/among_them", "--address:0.0.0.0", "--port:8123"]
    assert json.loads(cmd[3].removeprefix("--config:")) == {
        "seed": 17,
        "maxTicks": 99,
        "minPlayers": 8,
        "imposterCount": 2,
    }
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


def test_action_stat_key_marks_noop_and_non_noop_actions():
    assert bitworld_runner._action_stat_key(0) == "action.noop.success"
    assert bitworld_runner._action_stat_key(1) == "action.up.success"


def test_load_bitworld_policy_uses_policy_server_client_for_ws_uri(monkeypatch):
    captured: dict[str, object] = {}

    class _FakePolicyServerClient:
        def __init__(self, env_interface, *, url: str, agent_ids: list[int]):
            captured["env_interface"] = env_interface
            captured["url"] = url
            captured["agent_ids"] = agent_ids

    monkeypatch.setattr(bitworld_runner, "WebSocketRawPolicyServerClient", _FakePolicyServerClient)

    loaded_policy = bitworld_runner._load_bitworld_policy(
        "ws://127.0.0.1:9000",
        agent_ids=[0, 3],
        num_agents=5,
    )

    assert loaded_policy.policy is not None
    assert loaded_policy.frame_stack == bitworld_runner.BITWORLD_DEFAULT_FRAME_STACK
    assert captured["url"] == "ws://127.0.0.1:9000"
    assert captured["agent_ids"] == [0, 3]
    env_interface = captured["env_interface"]
    assert env_interface.num_agents == 5
    assert env_interface.observation_kind == "pixels"


def test_load_bitworld_policy_uses_frame_stack_from_policy_server_uri(monkeypatch):
    captured: dict[str, object] = {}

    class _FakePolicyServerClient:
        def __init__(self, env_interface, *, url: str, agent_ids: list[int]):
            captured["env_interface"] = env_interface
            captured["url"] = url
            captured["agent_ids"] = agent_ids

    monkeypatch.setattr(bitworld_runner, "WebSocketRawPolicyServerClient", _FakePolicyServerClient)

    loaded_policy = bitworld_runner._load_bitworld_policy(
        "ws://127.0.0.1:9000?frame_stack=7",
        agent_ids=[1],
        num_agents=5,
    )

    assert loaded_policy.frame_stack == 7
    assert captured["env_interface"].observation_shape == (
        7,
        bitworld_runner.SCREEN_HEIGHT,
        bitworld_runner.SCREEN_WIDTH,
    )


def test_unpack_frame_expands_4bit_palette_indices():
    packed = bytes([0x21, 0xF0]) + bytes(bitworld_runner.PROTOCOL_BYTES - 2)

    frame = bitworld_runner.unpack_frame(packed)

    assert frame.shape == (bitworld_runner.SCREEN_HEIGHT, bitworld_runner.SCREEN_WIDTH)
    assert frame.dtype == np.uint8
    assert frame[0, :4].tolist() == [1, 2, 0, 15]


def test_unpack_frame_rejects_wrong_size():
    with pytest.raises(ValueError, match="BitWorld frames"):
        bitworld_runner.unpack_frame(b"\x00")


def test_bitworld_policy_env_interface_requires_submission_contract_for_data_policy(tmp_path):
    weights_path = tmp_path / "weights.safetensors"
    weights_path.write_bytes(b"not inspected")
    policy_spec = PolicySpec(class_path="metta.agent.policy.CheckpointPolicy", data_path=str(weights_path))

    with pytest.raises(ValueError, match="policy_env_interface"):
        bitworld_runner._bitworld_policy_env_interface(policy_spec)


def test_bitworld_policy_env_interface_uses_submission_contract():
    policy_spec = PolicySpec(
        class_path="metta.agent.policy.CheckpointPolicy",
        policy_env_interface=bitworld_runner._build_bitworld_env_interface(frame_stack=3),
    )

    env_interface, frame_stack = bitworld_runner._bitworld_policy_env_interface(policy_spec, num_agents=5)

    assert frame_stack == 3
    assert env_interface.observation_shape == (
        3,
        bitworld_runner.SCREEN_HEIGHT,
        bitworld_runner.SCREEN_WIDTH,
    )
    assert env_interface.num_agents == 5


def test_bitworld_policy_env_interface_defaults_for_class_policy():
    policy_spec = PolicySpec(class_path="mettagrid.policy.bitworld.BitWorldRandomDpadPolicy")

    env_interface, frame_stack = bitworld_runner._bitworld_policy_env_interface(policy_spec)

    assert frame_stack == bitworld_runner.BITWORLD_DEFAULT_FRAME_STACK
    assert env_interface.observation_shape == (
        bitworld_runner.BITWORLD_DEFAULT_FRAME_STACK,
        bitworld_runner.SCREEN_HEIGHT,
        bitworld_runner.SCREEN_WIDTH,
    )


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


def test_run_bitworld_episode_does_not_duplicate_reward_in_agent_stats(monkeypatch):
    frame = _pack_frame(np.zeros((bitworld_runner.SCREEN_HEIGHT, bitworld_runner.SCREEN_WIDTH), dtype=np.uint8))

    class _FixedActionPolicy:
        def step_batch(self, _observations: np.ndarray, actions: np.ndarray) -> None:
            actions[:] = 1

        def close(self) -> None:
            pass

    class _InlineThread:
        def __init__(self, target, args, daemon):
            del daemon
            self._target = target
            self._args = args

        def start(self) -> None:
            self._target(*self._args)

        def join(self, timeout: float | None = None) -> None:
            del timeout

    class _FakePlayerWebSocket:
        def recv(self) -> bytes:
            return frame

        def send(self, _data: bytes, _opcode: int) -> None:
            pass

        def close(self) -> None:
            pass

    class _FakeRewardWebSocket:
        def close(self) -> None:
            pass

    def fake_reward_listener(state: bitworld_runner.RewardState) -> None:
        with state.lock:
            state.rewards_by_address.update({f"player_{i}": float(i + 1) for i in range(5)})

    sockets = iter([cast(Any, _FakeRewardWebSocket()), *[_FakePlayerWebSocket() for _i in range(5)]])

    monkeypatch.setattr(bitworld_runner, "_find_bitworld_binary", lambda _config: Path("/tmp/bitworld/among_them"))
    monkeypatch.setattr(bitworld_runner, "_start_server_on_free_port", lambda _path, _config: _FakeProc(alive=True))
    monkeypatch.setattr(bitworld_runner, "_connect_websocket", lambda *_args, **_kwargs: next(sockets))
    monkeypatch.setattr(bitworld_runner, "_reward_listener", fake_reward_listener)
    monkeypatch.setattr(bitworld_runner.threading, "Thread", _InlineThread)
    monkeypatch.setattr(
        bitworld_runner,
        "_load_bitworld_policy",
        lambda _uri, _agent_ids, _num_agents: bitworld_runner.LoadedBitWorldPolicy(_FixedActionPolicy(), frame_stack=1),
    )

    result = bitworld_runner.run_bitworld_episode(
        PureSingleEpisodeJob(
            policy_uris=["fake_policy"],
            assignments=[0, 0, 0, 0, 0],
            env=MettaGridConfig(game={"num_agents": 5, "max_steps": 1}),
            game_engine="bitworld",
            results_uri=None,
            replay_uri=None,
            seed=17,
        )
    )

    assert result.rewards == [1.0, 2.0, 3.0, 4.0, 5.0]
    assert all("reward" not in agent_stats for agent_stats in result.stats["agent"])
    assert [agent_stats["action.a.success"] for agent_stats in result.stats["agent"]] == [1, 1, 1, 1, 1]


def _pack_frame(frame: np.ndarray) -> bytes:
    flat = frame.reshape(-1)
    return bytes((flat[0::2] | (flat[1::2] << 4)).tolist())
