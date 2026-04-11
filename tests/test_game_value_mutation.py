"""Tests for SetGameValueMutation."""

from mettagrid.config.game_value import InventoryValue, val
from mettagrid.config.handler_config import Handler
from mettagrid.config.mettagrid_config import MettaGridConfig, ResourceLimitsConfig
from mettagrid.config.mutation import EntityTarget, SetGameValueMutation
from mettagrid.simulator import Action, Simulation


def _make_sim(on_tick, resource_names: list[str], initial: dict[str, int]) -> Simulation:
    """Create a minimal simulation with one agent and on_tick handlers."""
    cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
        [
            ["#", "#", "#"],
            ["#", "@", "#"],
            ["#", "#", "#"],
        ],
        char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty"},
    )
    cfg.game.resource_names = resource_names
    cfg.game.agent.on_tick = on_tick
    cfg.game.agent.inventory.initial = initial
    cfg.game.agent.inventory.limits = {
        name: ResourceLimitsConfig(base=1000, resources=[name]) for name in resource_names
    }
    cfg.game.actions.noop.enabled = True
    return Simulation(cfg)


def test_const_delta_via_on_tick():
    """Test that SetGameValueMutation with static delta adds to inventory each tick."""
    sim = _make_sim(
        on_tick=Handler(
            name="add_energy",
            mutations=[
                SetGameValueMutation(
                    value=InventoryValue(item="energy"),
                    delta=7,
                    target=EntityTarget.ACTOR,
                )
            ],
        ),
        resource_names=["energy"],
        initial={"energy": 10},
    )

    sim.agent(0).set_action(Action(name="noop"))
    sim.step()
    assert sim.agent(0).inventory.get("energy", 0) == 17

    sim.agent(0).set_action(Action(name="noop"))
    sim.step()
    assert sim.agent(0).inventory.get("energy", 0) == 24


def test_inventory_source_via_on_tick():
    """Test that SetGameValueMutation with inventory source uses source value as delta."""
    sim = _make_sim(
        on_tick=Handler(
            name="solar_to_energy",
            mutations=[
                SetGameValueMutation(
                    value=InventoryValue(item="energy"),
                    source=InventoryValue(item="solar"),
                    target=EntityTarget.ACTOR,
                )
            ],
        ),
        resource_names=["energy", "solar"],
        initial={"energy": 10, "solar": 5},
    )

    # Each tick should add solar amount (5) to energy
    sim.agent(0).set_action(Action(name="noop"))
    sim.step()
    energy = sim.agent(0).inventory.get("energy", 0)
    assert energy == 15, f"Expected 15, got {energy}"

    sim.agent(0).set_action(Action(name="noop"))
    sim.step()
    energy = sim.agent(0).inventory.get("energy", 0)
    assert energy == 20, f"Expected 20, got {energy}"


def test_inventory_source_zero():
    """Test that SetGameValueMutation with zero-valued source adds nothing."""
    sim = _make_sim(
        on_tick=Handler(
            name="solar_to_energy",
            mutations=[
                SetGameValueMutation(
                    value=InventoryValue(item="energy"),
                    source=InventoryValue(item="solar"),
                    target=EntityTarget.ACTOR,
                )
            ],
        ),
        resource_names=["energy", "solar"],
        initial={"energy": 10, "solar": 0},
    )

    sim.agent(0).set_action(Action(name="noop"))
    sim.step()
    energy = sim.agent(0).inventory.get("energy", 0)
    assert energy == 10, f"Expected 10 (no change), got {energy}"


def test_const_source_via_on_tick():
    """Test that explicit ConstValue source works the same as static delta."""
    sim = _make_sim(
        on_tick=Handler(
            name="add_energy",
            mutations=[
                SetGameValueMutation(
                    value=InventoryValue(item="energy"),
                    source=val(3.0),
                    target=EntityTarget.ACTOR,
                )
            ],
        ),
        resource_names=["energy"],
        initial={"energy": 10},
    )

    sim.agent(0).set_action(Action(name="noop"))
    sim.step()
    energy = sim.agent(0).inventory.get("energy", 0)
    assert energy == 13, f"Expected 13, got {energy}"
