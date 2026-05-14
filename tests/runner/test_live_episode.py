from __future__ import annotations

import asyncio
from typing import Any

import numpy as np

from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.runner.live_episode import LiveMettaGridEpisode, LivePlayerConnection


class RecordingWebSocket:
    def __init__(self):
        self.sent: list[dict[str, Any]] = []
        self.close_code: int | None = None
        self.close_count = 0
        self.close_reason: str | None = None
        self._message_event = asyncio.Event()

    async def send_json(self, data):
        self.sent.append(dict(data))
        self._message_event.set()

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        self.close_count += 1
        self.close_code = code
        self.close_reason = reason

    async def wait_for_type(self, message_type: str) -> dict[str, Any]:
        while True:
            for message in self.sent:
                if message["type"] == message_type:
                    return message
            self._message_event.clear()
            await self._message_event.wait()

    async def wait_for_observation_step(self, step: int) -> dict[str, Any]:
        while True:
            for message in self.sent:
                if message["type"] == "observation" and message["step"] == step:
                    return message
            self._message_event.clear()
            await self._message_event.wait()


class BlockingConfigWebSocket:
    def __init__(self):
        self.sent: list[dict[str, Any]] = []
        self.config_send_started = asyncio.Event()
        self.allow_config_send = asyncio.Event()

    async def send_json(self, data):
        self.sent.append(dict(data))
        if data["type"] == "player_config":
            self.config_send_started.set()
            await self.allow_config_send.wait()

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        pass


class DisconnectingWebSocket:
    async def send_json(self, data):
        raise RuntimeError("disconnected")

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        pass


class FakeAgent:
    def __init__(self, sim: "FakeSimulation", agent_id: int):
        self.sim = sim
        self.agent_id = agent_id

    def set_action(self, action_name: str) -> None:
        self.sim.pending_actions[self.agent_id] = action_name


class FakeCSim:
    def __init__(self, sim: "FakeSimulation"):
        self.sim = sim

    def observations(self) -> np.ndarray:
        return np.asarray(
            [
                [[254, 1, self.sim.current_step], [255, 255, 255]],
                [[254, 1, self.sim.current_step], [255, 255, 255]],
            ],
            dtype=np.uint8,
        )


class FakeSimulation:
    def __init__(self):
        self.current_step = 0
        self.num_agents = 2
        self.episode_rewards = np.asarray([0.0, 0.0])
        self.pending_actions = ["noop", "noop"]
        self.step_actions: list[tuple[str, str]] = []
        self._c_sim = FakeCSim(self)

    def is_done(self) -> bool:
        return False

    def agent(self, agent_id: int) -> FakeAgent:
        return FakeAgent(self, agent_id)

    def step(self) -> None:
        self.step_actions.append(tuple(self.pending_actions))
        self.current_step += 1


def test_policy_action_flow_applies_latest_policy_action() -> None:
    async def run_test() -> None:
        episode = _episode()
        websocket = RecordingWebSocket()
        connection_id = await episode.connect_player(0, websocket)

        await episode.handle_player_message(
            connection_id,
            {"type": "action", "action_name": "move_north", "policy_infos": {"reason": "test"}},
        )
        episode.apply_actions()

        assert episode.sim.pending_actions[0] == "move_north"
        assert episode.latest_policy_actions[0].policy_infos == {"reason": "test"}

    asyncio.run(run_test())


def test_external_policy_action_uses_shared_action_flow() -> None:
    episode = _episode()

    episode.set_policy_action(
        0, {"action_name": "move_north", "policy_infos": {"source": "global"}}, connection_id="global"
    )
    episode.apply_actions()

    assert episode.sim.pending_actions[0] == "move_north"
    assert episode.latest_policy_actions[0].policy_infos == {"source": "global"}


def test_human_takeover_overrides_policy_then_release_resumes_policy() -> None:
    async def run_test() -> None:
        episode = _episode()
        websocket = RecordingWebSocket()
        connection_id = await episode.connect_player(0, websocket)
        await episode.handle_player_message(connection_id, {"type": "action", "action_name": "move_south"})
        assert episode.tick_mode == "fixed"

        episode.takeover(0, connection_id)
        assert episode.tick_mode == "tick_when_act"

        await episode.handle_player_message(connection_id, {"type": "action", "action_name": "move_north"})

        episode.apply_actions()
        assert episode.sim.pending_actions[0] == "move_north"

        episode.release_takeover(0, connection_id)
        episode.apply_actions()
        assert episode.sim.pending_actions[0] == "move_south"

    asyncio.run(run_test())


def test_takeover_is_connection_scoped_with_multiple_connections_per_slot() -> None:
    async def run_test() -> None:
        episode = _episode()
        policy_connection_id = await episode.connect_player(0, RecordingWebSocket())
        human_connection_id = await episode.connect_player(0, RecordingWebSocket())

        await episode.handle_player_message(policy_connection_id, {"type": "action", "action_name": "move_south"})
        episode.takeover(0, human_connection_id)
        await episode.handle_player_message(policy_connection_id, {"type": "action", "action_name": "move_south"})
        await episode.handle_player_message(human_connection_id, {"type": "action", "action_name": "move_north"})

        episode.apply_actions()
        assert episode.sim.pending_actions[0] == "move_north"

        episode.release_takeover(0, human_connection_id)
        episode.apply_actions()
        assert episode.sim.pending_actions[0] == "move_south"
        assert [c["connection_id"] for c in episode.slot_state(0)["connections"]] == [
            policy_connection_id,
            human_connection_id,
        ]

    asyncio.run(run_test())


def test_message_from_disconnected_connection_is_ignored() -> None:
    async def run_test() -> None:
        episode = _episode()
        connection_id = await episode.connect_player(0, RecordingWebSocket())
        episode.disconnect_player(connection_id)

        await episode.handle_player_message(connection_id, {"type": "action", "action_name": "move_north"})

        assert episode.latest_policy_actions[0].action_name == "noop"

    asyncio.run(run_test())


def test_boot_connection_disconnects_and_releases_takeover() -> None:
    async def run_test() -> None:
        episode = _episode()
        websocket = RecordingWebSocket()
        connection_id = await episode.connect_player(0, websocket)
        episode.takeover(0, connection_id)
        await episode.handle_player_message(connection_id, {"type": "action", "action_name": "move_north"})

        await episode.boot_connection(connection_id)

        assert websocket.close_code == 4000
        assert websocket.close_reason == "booted by admin"
        assert episode.connections == {}
        assert episode.connections_by_slot[0] == {}
        assert episode.human_controller_connection_ids[0] is None
        assert 0 not in episode.pending_human_actions

    asyncio.run(run_test())


def test_boot_connection_ignores_stale_connection_id() -> None:
    async def run_test() -> None:
        episode = _episode()
        websocket = RecordingWebSocket()
        connection_id = await episode.connect_player(0, websocket)

        await episode.boot_connection(connection_id)
        await episode.boot_connection(connection_id)
        await episode.boot_connection("missing")

        assert websocket.close_count == 1
        assert episode.connections == {}
        assert episode.connections_by_slot[0] == {}

    asyncio.run(run_test())


def test_connect_player_sends_config_before_receiving_observations() -> None:
    async def run_test() -> None:
        episode = _episode()
        websocket = BlockingConfigWebSocket()

        connect_task = asyncio.create_task(episode.connect_player(0, websocket))
        await websocket.config_send_started.wait()
        await episode.send_observations()

        assert [message["type"] for message in websocket.sent] == ["player_config"]

        websocket.allow_config_send.set()
        await connect_task
        await episode.send_observations()

        assert [message["type"] for message in websocket.sent] == ["player_config", "observation"]

    asyncio.run(run_test())


def test_wait_for_all_players_delays_autostart_until_every_slot_connects() -> None:
    async def run_test() -> None:
        episode = _episode(autostart=True, max_steps=1, wait_for_all_players=True)

        await episode.connect_player(0, RecordingWebSocket())
        await asyncio.sleep(0.02)

        assert episode.play_task is None
        assert episode.sim.current_step == 0

        await episode.connect_player(1, RecordingWebSocket())
        assert episode.play_task is not None
        await episode.play_task

        assert episode.sim.step_actions == [("noop", "noop")]

    asyncio.run(run_test())


def test_policy_action_timeout_waits_for_current_step_responses_and_noops_missing() -> None:
    async def run_test() -> None:
        episode = _episode(max_steps=2, policy_action_timeout_seconds=0.1)
        websocket_0 = RecordingWebSocket()
        websocket_1 = RecordingWebSocket()
        connection_0 = await episode.connect_player(0, websocket_0)
        connection_1 = await episode.connect_player(1, websocket_1)

        run_task = asyncio.create_task(episode.run())
        await websocket_0.wait_for_observation_step(0)
        await websocket_1.wait_for_observation_step(0)
        await asyncio.sleep(0.02)
        assert episode.sim.current_step == 0

        await episode.handle_player_message(
            connection_0,
            {"type": "action", "action_name": "move_north", "request_id": "step-0"},
        )
        await asyncio.sleep(0.02)
        assert episode.sim.current_step == 0

        await episode.handle_player_message(
            connection_1,
            {"type": "action", "action_name": "move_south", "request_id": "step-0"},
        )
        await websocket_0.wait_for_observation_step(1)
        await websocket_1.wait_for_observation_step(1)
        assert episode.sim.step_actions == [("move_north", "move_south")]

        await asyncio.sleep(0.02)
        assert episode.sim.current_step == 1

        await episode.handle_player_message(
            connection_0,
            {"type": "action", "action_name": "move_south", "request_id": "step-1"},
        )
        await run_task

        assert episode.sim.step_actions == [
            ("move_north", "move_south"),
            ("move_south", "noop"),
        ]

    asyncio.run(run_test())


def test_policy_action_timeout_noops_disconnected_slot_without_waiting() -> None:
    async def run_test() -> None:
        episode = _episode(max_steps=1, policy_action_timeout_seconds=5.0)
        websocket_0 = RecordingWebSocket()
        websocket_1 = RecordingWebSocket()
        connection_0 = await episode.connect_player(0, websocket_0)
        connection_1 = await episode.connect_player(1, websocket_1)

        run_task = asyncio.create_task(episode.run())
        await websocket_0.wait_for_observation_step(0)
        await websocket_1.wait_for_observation_step(0)

        await episode.handle_player_message(
            connection_0,
            {"type": "action", "action_name": "move_north", "request_id": "step-0"},
        )
        await asyncio.sleep(0.02)
        assert episode.sim.current_step == 0

        episode.disconnect_player(connection_1)
        await asyncio.wait_for(run_task, timeout=0.5)

        assert episode.sim.step_actions == [("move_north", "noop")]

    asyncio.run(run_test())


def test_human_controlled_idle_slot_applies_noop() -> None:
    async def run_test() -> None:
        episode = _episode()
        websocket = RecordingWebSocket()
        connection_id = await episode.connect_player(0, websocket)
        await episode.handle_player_message(connection_id, {"type": "action", "action_name": "move_south"})
        episode.takeover(0, connection_id)

        episode.apply_actions()

        assert episode.sim.pending_actions[0] == "noop"

    asyncio.run(run_test())


def test_tick_when_act_waits_for_human_action() -> None:
    async def run_test() -> None:
        episode = _episode(tick_mode="tick_when_act", human_action_timeout_seconds=5.0, max_steps=1)
        websocket = RecordingWebSocket()
        connection_id = await episode.connect_player(0, websocket)
        episode.takeover(0, connection_id)

        run_task = asyncio.create_task(episode.run())
        await websocket.wait_for_type("observation")
        await asyncio.sleep(0)
        assert episode.sim.current_step == 0

        await episode.handle_player_message(connection_id, {"type": "action", "action_name": "move_north"})
        await run_task

        assert episode.sim.step_actions == [("move_north", "noop")]

    asyncio.run(run_test())


def test_tick_when_act_timeout_steps_idle_human_as_noop() -> None:
    async def run_test() -> None:
        episode = _episode(tick_mode="tick_when_act", human_action_timeout_seconds=0.01, max_steps=1)
        websocket = RecordingWebSocket()
        connection_id = await episode.connect_player(0, websocket)
        episode.takeover(0, connection_id)

        await episode.run()

        assert episode.sim.step_actions == [("noop", "noop")]

    asyncio.run(run_test())


def test_send_to_players_disconnects_failed_websocket() -> None:
    async def run_test() -> None:
        episode = _episode()
        connection = LivePlayerConnection(connection_id="player-0", slot=0, websocket=DisconnectingWebSocket())
        episode.connections[connection.connection_id] = connection
        episode.connections_by_slot[0][connection.connection_id] = connection

        await episode._send_to_players({"player-0": {"type": "observation"}})

        assert episode.connections == {}
        assert episode.connections_by_slot[0] == {}

    asyncio.run(run_test())


def _episode(
    *,
    tick_mode: str = "fixed",
    human_action_timeout_seconds: float = 5.0,
    max_steps: int = 3,
    autostart: bool = False,
    wait_for_all_players: bool = False,
    policy_action_timeout_seconds: float | None = None,
) -> LiveMettaGridEpisode:
    return LiveMettaGridEpisode(
        FakeSimulation(),
        PolicyEnvInterface(
            obs_features=[],
            tags=[],
            action_names=["noop", "move_north", "move_south"],
            num_agents=2,
            observation_shape=(2, 3),
            egocentric_shape=(1, 1),
        ),
        tokens=["token-0", "token-1"],
        max_steps=max_steps,
        step_seconds=0.01,
        tick_mode=tick_mode,
        human_action_timeout_seconds=human_action_timeout_seconds,
        autostart=autostart,
        wait_for_all_players=wait_for_all_players,
        policy_action_timeout_seconds=policy_action_timeout_seconds,
    )
