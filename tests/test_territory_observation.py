from mettagrid.config.filter import AlignmentFilter
from mettagrid.config.handler_config import (
    AlignmentCondition,
    AOEConfig,
    HandlerTarget,
)
from mettagrid.config.mettagrid_config import CollectiveConfig, GridObjectConfig, InventoryConfig, MettaGridConfig
from mettagrid.simulator import Simulation
from mettagrid.simulator.interface import Location
from mettagrid.test_support.observation_helper import ObservationHelper


def test_territory_observation_tokens_emitted_for_empty_cells() -> None:
    cfg = MettaGridConfig.EmptyRoom(num_agents=1, width=5, height=5, border_width=0).with_ascii_map(
        [
            ".....",
            "..E..",
            "..@..",
            "..F..",
            ".....",
        ],
        char_to_map_name={"E": "enemy_source", "F": "friendly_source"},
    )
    cfg.game.obs.width = 5
    cfg.game.obs.height = 5
    cfg.game.obs.num_tokens = 200
    cfg.game.obs.territory = True
    cfg.game.resource_names = []
    cfg.game.agent.collective = "cogs"
    cfg.game.collectives = {
        "cogs": CollectiveConfig(inventory=InventoryConfig()),
        "clips": CollectiveConfig(inventory=InventoryConfig()),
    }
    cfg.game.objects["friendly_source"] = GridObjectConfig(
        name="friendly_source",
        map_name="friendly_source",
        collective="cogs",
        aoes={
            "friendly": AOEConfig(
                radius=2,
                filters=[
                    AlignmentFilter(target=HandlerTarget.TARGET, alignment=AlignmentCondition.SAME_COLLECTIVE),
                ],
            )
        },
    )
    cfg.game.objects["enemy_source"] = GridObjectConfig(
        name="enemy_source",
        map_name="enemy_source",
        collective="clips",
        aoes={
            "enemy": AOEConfig(
                radius=2,
                filters=[
                    AlignmentFilter(target=HandlerTarget.TARGET, alignment=AlignmentCondition.DIFFERENT_COLLECTIVE),
                ],
            )
        },
    )

    sim = Simulation(cfg)
    obs = sim._c_sim.observations()[0]
    territory_feature_id = sim.config.game.id_map().feature_id("territory")

    # Center cell is a midpoint tie between cogs and clips, and clips loses ties.
    assert (
        ObservationHelper.find_token_values(
            obs, location=Location(2, 2), feature_id=territory_feature_id, is_global=False
        )
        == 0x01
    )

    # (4,4) is outside Euclidean radius 2 from (3,2): no token.
    assert (
        len(
            ObservationHelper.find_token_values(
                obs, location=Location(4, 4), feature_id=territory_feature_id, is_global=False
            )
        )
        == 0
    )

    # (4,3) is in range of the friendly source at (3,2) but out of range of the enemy at (1,2).
    assert (
        ObservationHelper.find_token_values(
            obs, location=Location(4, 3), feature_id=territory_feature_id, is_global=False
        )
        == 0x01
    )
