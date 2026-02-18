from mettagrid.config.filter import AlignmentFilter
from mettagrid.config.handler_config import (
    AlignmentCondition,
    AOEConfig,
    HandlerTarget,
)
from mettagrid.config.mettagrid_config import (
    CollectiveConfig,
    GridObjectConfig,
    InventoryConfig,
    MettaGridConfig,
    ResourceLimitsConfig,
)
from mettagrid.config.mutation import updateTarget
from mettagrid.simulator import Simulation


def test_enemy_aoe_applies_before_friendly_to_avoid_hp_clamp_artifacts() -> None:
    # If friendly heal is applied first, it clamps to max HP, then enemy damage reduces HP.
    # We want enemy damage first, then friendly heal, so the net result clamps correctly.
    cfg = MettaGridConfig.EmptyRoom(num_agents=1, width=5, height=5, border_width=0).with_ascii_map(
        [
            ".....",
            "..F..",  # friendly (registered earlier)
            "..@..",  # agent in range of both
            "..E..",  # enemy (registered later)
            ".....",
        ],
        char_to_map_name={"F": "friendly", "E": "enemy"},
    )
    cfg.game.resource_names = ["hp"]
    cfg.game.agent.collective = "cogs"
    cfg.game.agent.inventory = InventoryConfig(
        initial={"hp": 99},
        limits={"hp": ResourceLimitsConfig(min=100, max=100, resources=["hp"])},
    )
    cfg.game.collectives = {
        "cogs": CollectiveConfig(inventory=InventoryConfig()),
        "clips": CollectiveConfig(inventory=InventoryConfig()),
    }
    cfg.game.objects["friendly"] = GridObjectConfig(
        name="friendly",
        map_name="friendly",
        collective="cogs",
        aoes={
            "heal": AOEConfig(
                radius=2,
                filters=[
                    AlignmentFilter(target=HandlerTarget.TARGET, alignment=AlignmentCondition.SAME_COLLECTIVE),
                ],
                mutations=[updateTarget({"hp": +100})],
            ),
        },
    )
    cfg.game.objects["enemy"] = GridObjectConfig(
        name="enemy",
        map_name="enemy",
        collective="clips",
        aoes={
            "damage": AOEConfig(
                radius=2,
                filters=[
                    AlignmentFilter(
                        target=HandlerTarget.TARGET,
                        alignment=AlignmentCondition.DIFFERENT_COLLECTIVE,
                    ),
                ],
                mutations=[updateTarget({"hp": -10})],
            ),
        },
    )

    sim = Simulation(cfg)
    sim.agent(0).set_action("noop")
    sim.step()

    assert sim.agent(0).inventory.get("hp", 0) == 100
