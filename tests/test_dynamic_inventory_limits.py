"""Tests for dynamic inventory limits with modifiers.

This tests the feature where inventory limits can scale based on other items held.
For example, battery limit starts at 0, each gear adds +1 capacity.
The effective limit is: min(max, max(min, sum(modifier_bonus * quantity_held)))

Note: Integration tests for dynamic limits are done in C++ (test_has_inventory.cpp)
because Python's set_inventory uses unordered_map iteration which has undefined order.
"""

from mettagrid.config.mettagrid_config import (
    AgentConfig,
    GameConfig,
    InventoryConfig,
    MettaGridConfig,
    ResourceLimitsConfig,
)
from mettagrid.simulator import Simulation
from mettagrid.test_support.map_builders import ObjectNameMapBuilder


def test_resource_limits_config_with_modifiers():
    """Test that ResourceLimitsConfig correctly stores modifiers."""
    config = ResourceLimitsConfig(
        resources=["battery"],
        min=0,
        max=100,
        modifiers={"gear": 5, "wrench": 3},
    )

    assert config.resources == ["battery"]
    assert config.min == 0
    assert config.max == 100
    assert config.modifiers == {"gear": 5, "wrench": 3}


def test_resource_limits_config_default_modifiers():
    """Test that ResourceLimitsConfig has empty modifiers by default."""
    config = ResourceLimitsConfig(
        resources=["gold"],
        min=100,
    )

    assert config.resources == ["gold"]
    assert config.min == 100
    assert config.max == 65535  # default
    assert config.modifiers == {}


def test_resource_limits_config_model_dump():
    """Test that modifiers are correctly serialized in model_dump."""
    config = ResourceLimitsConfig(
        resources=["energy"],
        min=0,
        max=500,
        modifiers={"battery": 25},
    )

    dumped = config.model_dump()
    assert dumped["resources"] == ["energy"]
    assert dumped["min"] == 0
    assert dumped["max"] == 500
    assert dumped["modifiers"] == {"battery": 25}


def test_resource_limits_config_empty_modifiers_dump():
    """Test that empty modifiers are correctly serialized."""
    config = ResourceLimitsConfig(
        resources=["ore"],
        min=50,
    )

    dumped = config.model_dump()
    assert dumped["modifiers"] == {}
    assert dumped["min"] == 50
    assert dumped["max"] == 65535


def test_effective_limit_min_floor():
    """Test that min acts as a floor for effective limit.

    With modifiers={"gear": 10}, min=5, max=20:
    - 0 gear: modifier_sum=0, effective = min(20, max(5, 0)) = 5

    Note: Full modifier integration tests are in C++ (test_has_inventory.cpp)
    because Python's set_inventory uses unordered_map iteration which has
    undefined order when setting multiple items that depend on each other.
    """
    from mettagrid.simulator import Action

    cfg = MettaGridConfig(
        game=GameConfig(
            num_agents=1,
            resource_names=["gear", "battery"],
            agent=AgentConfig(
                inventory=InventoryConfig(
                    limits={
                        "gear": ResourceLimitsConfig(min=10, resources=["gear"]),
                        "battery": ResourceLimitsConfig(
                            min=5,
                            max=20,
                            resources=["battery"],
                            modifiers={"gear": 10},
                        ),
                    },
                    initial={"gear": 0, "battery": 0},
                ),
            ),
        ),
    )
    cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=[["agent.agent"]])

    sim = Simulation(cfg)
    agent = sim.agent(0)

    # With 0 gear: effective limit = min(20, max(5, 0*10)) = min(20, 5) = 5
    # Agent should be able to hold up to 5 batteries (capped by min floor)
    agent.set_inventory({"battery": 10})
    agent.set_action(Action(name="noop"))
    sim.step()
    inv = agent.inventory
    assert inv.get("battery", 0) == 5, f"With 0 gear, battery should cap at min=5, got {inv.get('battery', 0)}"


def test_effective_limit_max_cap():
    """Test that max acts as a cap for effective limit.

    With min=100 (no modifiers), max=50:
    - effective = min(50, max(100, 0)) = min(50, 100) = 50
    """
    from mettagrid.simulator import Action

    cfg = MettaGridConfig(
        game=GameConfig(
            num_agents=1,
            resource_names=["gold"],
            agent=AgentConfig(
                inventory=InventoryConfig(
                    limits={
                        "gold": ResourceLimitsConfig(
                            min=100,
                            max=50,
                            resources=["gold"],
                        ),
                    },
                    initial={"gold": 0},
                ),
            ),
        ),
    )
    cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=[["agent.agent"]])

    sim = Simulation(cfg)
    agent = sim.agent(0)

    # max=50 should cap the effective limit even when min is higher
    agent.set_inventory({"gold": 100})
    agent.set_action(Action(name="noop"))
    sim.step()
    inv = agent.inventory
    assert inv.get("gold", 0) == 50, f"Gold should cap at max=50, got {inv.get('gold', 0)}"
