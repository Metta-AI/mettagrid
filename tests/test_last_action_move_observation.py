from mettagrid.config.handler_config import Handler
from mettagrid.config.mettagrid_config import GameConfig, GridObjectConfig, MettaGridConfig, ObsConfig, WallConfig
from mettagrid.config.obs_config import GlobalObsConfig
from mettagrid.config.tag import Tag
from mettagrid.simulator import Simulation
from mettagrid.test_support.observation_helper import ObservationHelper


def test_last_action_move_observation_reflects_actual_location_change() -> None:
    # Move into a usable building can succeed but not change the agent's location. last_action_move should be 0.
    cfg = MettaGridConfig(
        game=GameConfig(
            num_agents=1,
            obs=ObsConfig(
                width=5,
                height=5,
                num_tokens=200,
                global_obs=GlobalObsConfig(last_action_move=True),
            ),
            max_steps=10,
            objects={
                "wall": WallConfig(tags=[Tag("wall")]),
                "station": GridObjectConfig(
                    name="station",
                    map_name="station",
                    on_use_handlers={
                        "use": Handler(),  # always succeeds, no movement
                    },
                ),
            },
            resource_names=[],
        )
    )
    cfg.with_ascii_map(
        [
            "#####",
            "#.S.#",
            "#.@.#",
            "#...#",
            "#####",
        ],
        char_to_map_name={"S": "station"},
    )

    sim = Simulation(cfg)
    last_action_move_feature_id = sim.config.game.id_map().feature_id("last_action_move")

    sim.agent(0).set_action("move_north")
    sim.step()
    assert sim.agent(0).last_action_success is True
    obs = sim._c_sim.observations()
    assert ObservationHelper.find_global_tokens(obs[0], feature_id=last_action_move_feature_id)[:, 2] == 0

    sim.agent(0).set_action("move_south")
    sim.step()
    assert sim.agent(0).last_action_success is True
    obs = sim._c_sim.observations()
    assert ObservationHelper.find_global_tokens(obs[0], feature_id=last_action_move_feature_id)[:, 2] == 1
