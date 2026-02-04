from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    GameConfig,
    GlobalObsConfig,
    MettaGridConfig,
    MoveActionConfig,
    NoopActionConfig,
    ObsConfig,
    WallConfig,
)
from mettagrid.config.tag import Tag
from mettagrid.map_builder.ascii import AsciiMapBuilder
from mettagrid.mapgen.utils.ascii_grid import DEFAULT_CHAR_TO_NAME
from mettagrid.simulator import Location, Simulation
from mettagrid.test_support import ObservationHelper

NUM_OBS_TOKENS = 50


def xy(x: int, y: int) -> Location:
    return Location(row=y, col=x)


def _make_sim(game_map: list[list[str]], num_agents: int) -> Simulation:
    cfg = MettaGridConfig(
        game=GameConfig(
            num_agents=num_agents,
            obs=ObsConfig(
                width=11,
                height=11,
                num_tokens=NUM_OBS_TOKENS,
                global_obs=GlobalObsConfig(
                    episode_completion_pct=False,
                    last_action=False,
                    last_reward=False,
                ),
            ),
            max_steps=100,
            actions=ActionsConfig(noop=NoopActionConfig(), move=MoveActionConfig()),
            objects={"wall": WallConfig(tags=[Tag("wall")])},
            resource_names=[],
            map_builder=AsciiMapBuilder.Config(
                map_data=game_map,
                char_to_map_name=DEFAULT_CHAR_TO_NAME,
            ),
        )
    )
    return Simulation(cfg)


def _get_agent_id_at_location(sim: Simulation, obs, agent_idx: int, location: Location) -> int | None:
    helper = ObservationHelper()
    id_map = sim.config.game.id_map()

    fid = id_map.feature_id("agent_id")
    values = helper.find_token_values(obs[agent_idx], location=location, feature_id=fid)
    if len(values) > 0:
        return int(values[0])
    return None


class TestAgentIdObservation:
    def test_agents_see_own_ids(self):
        game_map = [
            ["#", "#", "#", "#", "#", "#", "#"],
            ["#", "@", ".", "@", ".", "@", "#"],
            ["#", "#", "#", "#", "#", "#", "#"],
        ]
        sim = _make_sim(game_map, num_agents=3)

        for i in range(3):
            sim.agent(i).set_action("noop")
        sim.step()
        obs = sim._c_sim.observations()

        center = xy(sim.config.game.obs.width // 2, sim.config.game.obs.height // 2)
        for agent_idx in range(3):
            agent_id = _get_agent_id_at_location(sim, obs, agent_idx=agent_idx, location=center)
            assert agent_id == agent_idx, f"Expected agent {agent_idx} to see agent_id={agent_idx}, got {agent_id}"

    def test_agents_see_other_agents_ids(self):
        game_map = [
            ["#", "#", "#", "#", "#"],
            ["#", "@", "@", ".", "#"],
            ["#", "#", "#", "#", "#"],
        ]
        sim = _make_sim(game_map, num_agents=2)

        for i in range(2):
            sim.agent(i).set_action("noop")
        sim.step()
        obs = sim._c_sim.observations()

        center = xy(sim.config.game.obs.width // 2, sim.config.game.obs.height // 2)

        agent_1_from_agent_0 = xy(center.col + 1, center.row)
        agent_0_from_agent_1 = xy(center.col - 1, center.row)

        observed_id = _get_agent_id_at_location(sim, obs, agent_idx=0, location=agent_1_from_agent_0)
        assert observed_id == 1, f"Agent 0 should see agent 1's ID at east, got {observed_id}"

        observed_id = _get_agent_id_at_location(sim, obs, agent_idx=1, location=agent_0_from_agent_1)
        assert observed_id == 0, f"Agent 1 should see agent 0's ID at west, got {observed_id}"
