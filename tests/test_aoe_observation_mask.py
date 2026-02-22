from mettagrid.config.mettagrid_config import GridObjectConfig, MettaGridConfig
from mettagrid.config.territory_config import TerritoryConfig, TerritoryControlConfig
from mettagrid.simulator import Simulation
from mettagrid.simulator.interface import Location
from mettagrid.test_support.observation_helper import ObservationHelper


def test_aoe_mask_observation_tokens_emitted_for_empty_cells() -> None:
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
    cfg.game.obs.aoe_mask = True
    cfg.game.resource_names = []
    cfg.game.agent.tags = ["team:cogs"]
    cfg.game.tags = ["team:cogs", "team:clips"]
    cfg.game.territories = {"team_territory": TerritoryConfig(tag_prefix="team:")}
    cfg.game.objects["friendly_source"] = GridObjectConfig(
        name="friendly_source",
        map_name="friendly_source",
        tags=["team:cogs"],
        territory_controls=[
            TerritoryControlConfig(territory="team_territory", strength=2),
        ],
    )
    cfg.game.objects["enemy_source"] = GridObjectConfig(
        name="enemy_source",
        map_name="enemy_source",
        tags=["team:clips"],
        territory_controls=[
            TerritoryControlConfig(territory="team_territory", strength=2),
        ],
    )

    sim = Simulation(cfg)
    obs = sim._c_sim.observations()[0]
    aoe_mask_feature_id = sim.config.game.id_map().feature_id("aoe_mask")

    # Center cell (2,2) equidistant from both → tie → neutral → no token.
    assert (
        len(
            ObservationHelper.find_token_values(
                obs, location=Location(2, 2), feature_id=aoe_mask_feature_id, is_global=False
            )
        )
        == 0
    )

    # (4,4) is beyond effective radius from both sources: no token.
    assert (
        len(
            ObservationHelper.find_token_values(
                obs, location=Location(4, 4), feature_id=aoe_mask_feature_id, is_global=False
            )
        )
        == 0
    )

    # (4,3) is distance ~1.4 from friendly source at (3,2) → score = max(0, 2-1.4) > 0.
    # Enemy at (1,2), distance ~3.2 from (4,3) → score = max(0, 2-3.2) = 0.
    # Friendly wins → mask = 1.
    assert (
        ObservationHelper.find_token_values(
            obs, location=Location(4, 3), feature_id=aoe_mask_feature_id, is_global=False
        )
        == 0x01
    )
