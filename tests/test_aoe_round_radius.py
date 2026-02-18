from mettagrid.config.handler_config import AOEConfig
from mettagrid.config.mettagrid_config import (
    GridObjectConfig,
    MettaGridConfig,
    ResourceLimitsConfig,
)
from mettagrid.config.mutation import updateTarget
from mettagrid.simulator import Simulation


def test_round_aoe_uses_euclidean_distance() -> None:
    def make_cfg(map_data: list[str]) -> MettaGridConfig:
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            map_data,
            char_to_map_name={"S": "aoe_source"},
        )
        cfg.game.resource_names = ["energy"]
        cfg.game.actions.noop.enabled = True
        cfg.game.agent.inventory.initial = {"energy": 0}
        cfg.game.agent.inventory.limits = {"energy": ResourceLimitsConfig(min=1000, resources=["energy"])}
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes={
                "round": AOEConfig(
                    radius=2,
                    is_round=True,
                    mutations=[updateTarget({"energy": 10})],
                )
            },
        )
        return cfg

    # Agent at Chebyshev distance 2 (dr=1, dc=2) but Euclidean distance > 2, so round AOE should not apply.
    cfg_out = make_cfg(["#######", "#.....#", "#.....#", "#..S..#", "#....@#", "#.....#", "#######"])
    sim_out = Simulation(cfg_out)
    sim_out.agent(0).set_action("noop")
    sim_out.step()
    assert sim_out.agent(0).inventory.get("energy", 0) == 0

    # Agent at Euclidean distance 2 (dr=2, dc=0), so round AOE should apply.
    cfg_in = make_cfg(["#######", "#.....#", "#.....#", "#..S..#", "#.....#", "#..@..#", "#######"])
    sim_in = Simulation(cfg_in)
    sim_in.agent(0).set_action("noop")
    sim_in.step()
    assert sim_in.agent(0).inventory.get("energy", 0) == 10
