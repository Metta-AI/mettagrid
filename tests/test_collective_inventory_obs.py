"""Test that collective inventory observations via inv() report correct values.

Regression test for a bug where InventoryValue with collective scope generated
a stat name 'collective.{resource}.amount' but the Collective stats tracker
only stores '{resource}.amount' (without 'collective.' prefix), causing
collective inventory observations to always read 0.
"""

from mettagrid.config.game_value import inv
from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    AgentConfig,
    CollectiveConfig,
    GameConfig,
    InventoryConfig,
    MettaGridConfig,
    NoopActionConfig,
    ResourceLimitsConfig,
)
from mettagrid.config.obs_config import GlobalObsConfig, ObsConfig
from mettagrid.simulator import Simulation
from mettagrid.test_support.map_builders import ObjectNameMapBuilder


def _make_sim_with_collective_inv_obs(initial_gold: int = 100) -> Simulation:
    """Create a minimal simulation with collective inventory obs via inv()."""
    game_config = GameConfig(
        num_agents=1,
        max_steps=10,
        resource_names=["gold"],
        actions=ActionsConfig(noop=NoopActionConfig()),
        collectives={
            "team": CollectiveConfig(
                inventory=InventoryConfig(
                    initial={"gold": initial_gold},
                    limits={"gold": ResourceLimitsConfig(min=10000, resources=["gold"])},
                ),
            ),
        },
        agent=AgentConfig(collective="team"),
        obs=ObsConfig(
            global_obs=GlobalObsConfig(
                obs=[inv("collective.gold")],
            )
        ),
        map_builder=ObjectNameMapBuilder.Config(map_data=[["agent.agent"]]),
    )

    return Simulation(MettaGridConfig(game=game_config), seed=42)


def test_collective_inv_obs_reflects_initial_inventory():
    """inv('collective.gold') should observe the collective's actual inventory."""
    sim = _make_sim_with_collective_inv_obs(initial_gold=100)
    agent = sim.agent(0)
    obs = agent.observation

    # Find the collective inventory token
    inv_tokens = [t for t in obs.tokens if "collective" in t.feature.name and "gold" in t.feature.name]
    assert len(inv_tokens) >= 1, f"No collective gold obs token found. Features: {[t.feature.name for t in obs.tokens]}"

    assert inv_tokens[0].value == 100, (
        f"Expected collective gold=100, got {inv_tokens[0].value}. "
        f"If 0, the stat name mapping in mettagrid_c_config.py is wrong."
    )

    sim.close()
