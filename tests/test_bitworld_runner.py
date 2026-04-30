import io
import json
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest

from mettagrid.bitworld import pack_chat_packet
from mettagrid.config.any_env_config import resolve_env_config_type
from mettagrid.config.bitworld_config import BitWorldEnvConfig
from mettagrid.policy.policy import PolicySpec
from mettagrid.runner import bitworld_runner
from mettagrid.runner.policy_server.websocket_transport import PolicyStepError
from mettagrid.runner.types import PureSingleEpisodeJob
from mettagrid.util.uri_resolvers import schemes as uri_schemes


def test_find_bitworld_binary_uses_container_layout(monkeypatch):
    expected = Path("/opt/bitworld/among_them/among_them")
    monkeypatch.setattr(Path, "exists", lambda path: path == expected)

    assert bitworld_runner._find_bitworld_binary("among_them") == expected


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
    replay_path = Path("/tmp/replay.json.z")

    monkeypatch.setattr(bitworld_runner, "_pick_free_port", lambda: next(ports))
    monkeypatch.setattr(bitworld_runner.time, "sleep", lambda _seconds: None)

    def fake_start_server(
        _binary_path: Path,
        runtime: bitworld_runner.BitWorldRuntime,
        _env: BitWorldEnvConfig,
        *,
        replay_path: Path | None = None,
    ) -> _FakeProc:
        started_ports.append(runtime.port)
        assert replay_path == Path("/tmp/replay.json.z")
        return _FakeProc(alive=len(started_ports) == 2)

    monkeypatch.setattr(bitworld_runner, "_start_server", fake_start_server)

    runtime = bitworld_runner.BitWorldRuntime()
    env = BitWorldEnvConfig(num_players=5)
    server_proc = bitworld_runner._start_server_on_free_port(
        Path("/tmp/bitworld"), runtime, env, replay_path=replay_path
    )

    assert server_proc.poll() is None
    assert started_ports == [1001, 1002]
    assert runtime.port == 1002


def test_bitworld_env_config_num_agents():
    env = BitWorldEnvConfig(num_players=5)
    assert env.num_agents == 5
    assert env.game_engine == "bitworld"


def test_bitworld_env_config_defaults():
    env = BitWorldEnvConfig()
    assert env.game_engine == "bitworld"
    assert env.game_name == "among_them"
    assert env.tasks_per_player == 8
    assert env.imposter_cooldown_ticks == 1200
    assert env.vote_timer_ticks == 600


def test_resolve_env_config_type_dispatches_static_methods():
    bw_dict = {"game_engine": "bitworld", "max_ticks": 500, "num_players": 3, "seed": 0}
    bw_type = resolve_env_config_type(bw_dict)
    assert bw_type.get_max_steps(bw_dict) == 500
    assert bw_type.get_num_agents(bw_dict) == 3
    bw_type.set_max_steps(bw_dict, 999)
    assert bw_dict["max_ticks"] == 999

    mg_dict = {"game": {"max_steps": 1000, "num_agents": 24, "map_builder": {"seed": 0}}}
    mg_type = resolve_env_config_type(mg_dict)
    assert mg_type.get_max_steps(mg_dict) == 1000
    assert mg_type.get_num_agents(mg_dict) == 24
    mg_type.set_map_seed(mg_dict, 42)
    assert mg_dict["game"]["map_builder"]["seed"] == 42


def test_start_server_uses_among_them_multi_player_config(monkeypatch):
    captured: dict[str, object] = {}

    def fake_popen(cmd, cwd, stdout, stderr):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["stdout"] = stdout
        captured["stderr"] = stderr
        return _FakeProc(alive=True)

    monkeypatch.setattr(bitworld_runner.subprocess, "Popen", fake_popen)

    runtime = bitworld_runner.BitWorldRuntime(host="0.0.0.0", port=8123)
    env = BitWorldEnvConfig(
        seed=17,
        max_ticks=99,
        num_players=8,
        imposter_count=2,
        tasks_per_player=3,
        task_complete_ticks=36,
        imposter_cooldown_ticks=240,
        vote_timer_ticks=120,
    )
    replay_path = Path("/tmp/replay.json.z")
    server_proc = bitworld_runner._start_server(
        Path("/tmp/bitworld/among_them"),
        runtime,
        env,
        replay_path=replay_path,
    )

    cmd = cast(list[str], captured["cmd"])
    assert server_proc.poll() is None
    assert cmd[:3] == ["/tmp/bitworld/among_them", "--address:0.0.0.0", "--port:8123"]
    assert json.loads(cmd[3].removeprefix("--config:")) == {
        "seed": 17,
        "maxTicks": 99,
        "minPlayers": 8,
        "imposterCount": 2,
        "tasksPerPlayer": 3,
        "imposterCooldownTicks": 240,
        "voteTimerTicks": 120,
        "taskCompleteTicks": 36,
    }
    assert cmd[4] == "--save-replay:/tmp/replay.json.z"
    assert captured["cwd"] == "/tmp/bitworld"


def test_replay_path_from_file_uri(tmp_path):
    replay_path = tmp_path / "replay.json.z"

    assert bitworld_runner._replay_path_from_uri(replay_path.as_uri()) == replay_path


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
        bitworld_runner.BitWorldRuntime(port=8123),
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


def test_load_bitworld_policy_uses_frame_stack_query_for_data_policy(monkeypatch):
    captured: dict[str, object] = {}
    policy_spec = PolicySpec(class_path="fake.Policy")

    def fake_policy_spec_from_uri(uri: str) -> PolicySpec:
        captured["uri"] = uri
        return policy_spec

    def fake_initialize_or_load_policy(env_interface, incoming_policy_spec):
        captured["env_interface"] = env_interface
        captured["policy_spec"] = incoming_policy_spec
        return object()

    monkeypatch.setattr(uri_schemes, "policy_spec_from_uri", fake_policy_spec_from_uri)
    monkeypatch.setattr("mettagrid.policy.loader.initialize_or_load_policy", fake_initialize_or_load_policy)

    loaded_policy = bitworld_runner._load_bitworld_policy(
        "metta://policy/amongthem_cyborg?frame_stack=1&llm_talk=false",
        agent_ids=[0],
        num_agents=5,
    )

    assert loaded_policy.frame_stack == 1
    assert captured["uri"] == "metta://policy/amongthem_cyborg?llm_talk=false"
    assert captured["policy_spec"] == policy_spec
    assert captured["env_interface"].observation_shape == (
        1,
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


def test_bitworld_policy_env_interface_comes_from_game_contract():
    env_interface, frame_stack = bitworld_runner._bitworld_policy_env_interface(num_agents=5)

    assert frame_stack == bitworld_runner.BITWORLD_DEFAULT_FRAME_STACK
    assert env_interface.observation_shape == (
        bitworld_runner.BITWORLD_DEFAULT_FRAME_STACK,
        bitworld_runner.SCREEN_HEIGHT,
        bitworld_runner.SCREEN_WIDTH,
    )
    assert env_interface.num_agents == 5


def test_load_bitworld_policy_passes_game_contract_to_data_policy(monkeypatch):
    captured: dict[str, object] = {}
    policy_spec = PolicySpec(
        class_path="metta.agent.policy.CheckpointPolicy",
        data_path="weights.safetensors",
        policy_env_interface=bitworld_runner._build_bitworld_env_interface(frame_stack=2),
    )

    monkeypatch.setattr(uri_schemes, "policy_spec_from_uri", lambda _uri: policy_spec)

    def fake_initialize_or_load_policy(env_interface, incoming_policy_spec):
        captured["env_interface"] = env_interface
        captured["policy_spec"] = incoming_policy_spec
        return object()

    monkeypatch.setattr("mettagrid.policy.loader.initialize_or_load_policy", fake_initialize_or_load_policy)

    loaded_policy = bitworld_runner._load_bitworld_policy(
        "file:///tmp/policy.zip?frame_stack=2", agent_ids=[0], num_agents=5
    )

    assert loaded_policy.frame_stack == 2
    assert captured["policy_spec"] == policy_spec
    assert captured["env_interface"].observation_shape == (
        2,
        bitworld_runner.SCREEN_HEIGHT,
        bitworld_runner.SCREEN_WIDTH,
    )
    assert captured["env_interface"].num_agents == 5


def test_policy_action_masks_rejects_invalid_policy_actions():
    class _InvalidActionPolicy:
        def step_batch(self, _observations: np.ndarray, actions: np.ndarray) -> None:
            actions[:] = bitworld_runner.BITWORLD_ACTION_COUNT

    observations = np.zeros(
        (1, bitworld_runner.BITWORLD_DEFAULT_FRAME_STACK, bitworld_runner.SCREEN_HEIGHT, bitworld_runner.SCREEN_WIDTH),
        dtype=np.uint8,
    )

    with pytest.raises(PolicyStepError, match="BitWorld policy action index"):
        bitworld_runner._policy_action_masks(cast(Any, _InvalidActionPolicy()), observations, [0])


def test_policy_step_actions_passes_frame_advances_to_capable_policy():
    class _FrameAdvancePolicy:
        def step_batch_for_agents_with_frame_advances(
            self,
            agent_ids: list[int],
            _observations: np.ndarray,
            actions: np.ndarray,
            frame_advances: np.ndarray,
        ) -> None:
            self.agent_ids = list(agent_ids)
            self.frame_advances = frame_advances.copy()
            actions[:] = 1

    observations = np.zeros(
        (2, bitworld_runner.BITWORLD_DEFAULT_FRAME_STACK, bitworld_runner.SCREEN_HEIGHT, bitworld_runner.SCREEN_WIDTH),
        dtype=np.uint8,
    )
    actions = np.zeros(2, dtype=np.int64)
    frame_advances = np.asarray([1, 37], dtype=np.int32)
    policy = _FrameAdvancePolicy()

    bitworld_runner._policy_step_actions(cast(Any, policy), observations, actions, [0, 4], frame_advances)

    assert policy.agent_ids == [0, 4]
    assert policy.frame_advances.tolist() == [1, 37]
    assert actions.tolist() == [1, 1]


def test_policy_debug_stats_are_opt_in(monkeypatch):
    class _DebugPolicy:
        def __init__(self):
            self.calls = 0

        def bitworld_debug_stats(self, agent_ids: list[int]) -> list[dict[str, float]]:
            self.calls += 1
            return [{"agent": float(agent_id)} for agent_id in agent_ids]

    policy = _DebugPolicy()

    monkeypatch.delenv(bitworld_runner.DEBUG_STATS_ENV, raising=False)
    assert bitworld_runner._policy_debug_stats(cast(Any, policy), [2]) == [{}]
    assert policy.calls == 0

    monkeypatch.setenv(bitworld_runner.DEBUG_STATS_ENV, "1")
    assert bitworld_runner._policy_debug_stats(cast(Any, policy), [2]) == [{"agent": 2.0}]
    assert policy.calls == 1


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


def test_receive_player_frame_uses_latest_frame_under_small_backlog():
    frames = []
    for value in range(3):
        frame = np.full((bitworld_runner.SCREEN_HEIGHT, bitworld_runner.SCREEN_WIDTH), value, dtype=np.uint8)
        frames.append(_pack_frame(frame))

    class _FrameQueueWebSocket:
        def __init__(self):
            self.timeout = 2.0

        def gettimeout(self) -> float:
            return self.timeout

        def settimeout(self, timeout: float) -> None:
            self.timeout = timeout

        def recv(self) -> bytes:
            if frames:
                return frames.pop(0)
            raise bitworld_runner.websocket.WebSocketTimeoutException()

    conn = bitworld_runner.PlayerConnection(ws=cast(Any, _FrameQueueWebSocket()), player_index=0, address="player_0")

    frame_data, frame_advance = bitworld_runner._receive_player_frame(conn)

    assert frame_advance == 3
    assert frame_data == _pack_frame(
        np.full((bitworld_runner.SCREEN_HEIGHT, bitworld_runner.SCREEN_WIDTH), 2, dtype=np.uint8)
    )
    assert conn.queued_frames == []


def test_receive_player_frame_drains_to_latest_under_large_backlog():
    frames = []
    frame_count = 35
    for value in range(frame_count):
        frame = np.full((bitworld_runner.SCREEN_HEIGHT, bitworld_runner.SCREEN_WIDTH), value % 16, dtype=np.uint8)
        frames.append(_pack_frame(frame))

    class _FrameQueueWebSocket:
        def __init__(self):
            self.timeout = 2.0

        def gettimeout(self) -> float:
            return self.timeout

        def settimeout(self, timeout: float) -> None:
            self.timeout = timeout

        def recv(self) -> bytes:
            if frames:
                return frames.pop(0)
            raise bitworld_runner.websocket.WebSocketTimeoutException()

    conn = bitworld_runner.PlayerConnection(ws=cast(Any, _FrameQueueWebSocket()), player_index=0, address="player_0")

    frame_data, frame_advance = bitworld_runner._receive_player_frame(conn)

    assert frame_advance == frame_count
    assert frame_data == _pack_frame(
        np.full((bitworld_runner.SCREEN_HEIGHT, bitworld_runner.SCREEN_WIDTH), 2, dtype=np.uint8)
    )
    assert conn.queued_frames == []


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
        def __init__(self):
            self.timeout = 2.0

        def gettimeout(self) -> float:
            return self.timeout

        def settimeout(self, timeout: float) -> None:
            self.timeout = timeout

        def recv(self) -> bytes:
            if self.timeout == 0.0:
                raise bitworld_runner.websocket.WebSocketTimeoutException()
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

    monkeypatch.setattr(bitworld_runner, "_find_bitworld_binary", lambda _game_name: Path("/tmp/bitworld/among_them"))
    monkeypatch.setattr(
        bitworld_runner,
        "_start_server_on_free_port",
        lambda _path, _runtime, _env, **_kwargs: _FakeProc(alive=True),
    )
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
            env=BitWorldEnvConfig(num_players=5, max_ticks=1),
            results_uri=None,
            replay_uri=None,
            seed=17,
        )
    )

    assert result.rewards == [1.0, 2.0, 3.0, 4.0, 5.0]
    assert all("reward" not in agent_stats for agent_stats in result.stats["agent"])
    assert [agent_stats["action.a.success"] for agent_stats in result.stats["agent"]] == [1, 1, 1, 1, 1]


def test_run_bitworld_episode_sends_policy_chat(monkeypatch):
    frame = _pack_frame(np.zeros((bitworld_runner.SCREEN_HEIGHT, bitworld_runner.SCREEN_WIDTH), dtype=np.uint8))

    class _TalkingPolicy:
        def step_batch_for_agents(self, agent_ids: list[int], _observations: np.ndarray, actions: np.ndarray) -> None:
            self.agent_ids = list(agent_ids)
            actions[:] = 1

        def bitworld_chat_messages(self, agent_ids: list[int]) -> list[str | None]:
            return ["body in medbay" if agent_id == 0 else None for agent_id in agent_ids]

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
        def __init__(self):
            self.sent: list[bytes] = []
            self.timeout = 2.0

        def gettimeout(self) -> float:
            return self.timeout

        def settimeout(self, timeout: float) -> None:
            self.timeout = timeout

        def recv(self) -> bytes:
            if self.timeout == 0.0:
                raise bitworld_runner.websocket.WebSocketTimeoutException()
            return frame

        def send(self, data: bytes, _opcode: int) -> None:
            self.sent.append(data)

        def close(self) -> None:
            pass

    class _FakeRewardWebSocket:
        def close(self) -> None:
            pass

    def fake_reward_listener(_state: bitworld_runner.RewardState) -> None:
        pass

    player_sockets = [_FakePlayerWebSocket() for _i in range(5)]
    sockets = iter([cast(Any, _FakeRewardWebSocket()), *player_sockets])

    monkeypatch.setattr(bitworld_runner, "_find_bitworld_binary", lambda _game_name: Path("/tmp/bitworld/among_them"))
    monkeypatch.setattr(
        bitworld_runner,
        "_start_server_on_free_port",
        lambda _path, _runtime, _env, **_kwargs: _FakeProc(alive=True),
    )
    monkeypatch.setattr(bitworld_runner, "_connect_websocket", lambda *_args, **_kwargs: next(sockets))
    monkeypatch.setattr(bitworld_runner, "_reward_listener", fake_reward_listener)
    monkeypatch.setattr(bitworld_runner.threading, "Thread", _InlineThread)
    monkeypatch.setattr(
        bitworld_runner,
        "_load_bitworld_policy",
        lambda _uri, _agent_ids, _num_agents: bitworld_runner.LoadedBitWorldPolicy(_TalkingPolicy(), frame_stack=1),
    )

    result = bitworld_runner.run_bitworld_episode(
        PureSingleEpisodeJob(
            policy_uris=["fake_policy"],
            assignments=[0, 0, 0, 0, 0],
            env=BitWorldEnvConfig(num_players=5, max_ticks=1),
            results_uri=None,
            replay_uri=None,
        )
    )

    assert pack_chat_packet("body in medbay") in player_sockets[0].sent
    assert all(pack_chat_packet("body in medbay") not in socket.sent for socket in player_sockets[1:])
    assert result.stats["agent"][0]["chat.sent"] == 1.0


def _pack_frame(frame: np.ndarray) -> bytes:
    flat = frame.reshape(-1)
    return bytes((flat[0::2] | (flat[1::2] << 4)).tolist())
