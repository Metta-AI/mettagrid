"""Tests for AOETracker functionality - movement in/out, presence_deltas, and agent AOE.

These tests verify that:
1. AOE mutations fire when agents are in range
2. presence_deltas apply resource changes on enter/exit events
3. Agent AOE (mobile) works correctly with is_static=False
4. Effect_self flag controls whether source is affected by its own AOE
"""

from mettagrid.config.handler_config import AOEConfig
from mettagrid.config.mettagrid_config import (
    GridObjectConfig,
    MettaGridConfig,
    ResourceLimitsConfig,
)
from mettagrid.config.mutation import EntityTarget, ResourceDeltaMutation
from mettagrid.simulator import Simulation


class TestAOEMutations:
    """Test that AOE mutations fire correctly."""

    def test_aoe_mutation_fires_each_step(self):
        """AOE mutation should fire each step the agent is in range."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent
                ["#", ".", "S", ".", "#"],  # AOE source
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "charger"},
        )

        cfg.game.resource_names = ["energy"]
        cfg.game.agent.inventory.initial = {"energy": 0}
        cfg.game.agent.inventory.limits = {
            "energy": ResourceLimitsConfig(min=1000, resources=["energy"]),
        }
        # No on_tick — no passive regen
        cfg.game.actions.noop.enabled = True

        # AOE source that gives energy each tick
        cfg.game.objects["charger"] = GridObjectConfig(
            name="charger",
            map_name="charger",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)

        # Step 1
        sim.agent(0).set_action("noop")
        sim.step()
        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 10, f"Step 1: expected 10 energy, got {energy}"

        # Step 2
        sim.agent(0).set_action("noop")
        sim.step()
        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 20, f"Step 2: expected 20 energy, got {energy}"

        # Step 3
        sim.agent(0).set_action("noop")
        sim.step()
        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 30, f"Step 3: expected 30 energy, got {energy}"


class TestPresenceDeltas:
    """Test presence_deltas (enter/exit resource changes)."""

    def test_presence_delta_applied_on_enter(self):
        """When agent enters AOE, presence_delta should add resources."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#", "#", "#"],
                ["#", "@", ".", ".", ".", "S", "#"],  # Agent starts far from AOE source
                ["#", "#", "#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "buffer"},
        )

        cfg.game.resource_names = ["shield"]
        cfg.game.agent.inventory.initial = {"shield": 0}
        cfg.game.agent.inventory.limits = {
            "shield": ResourceLimitsConfig(min=1000, resources=["shield"]),
        }
        # No on_tick — no passive regen
        cfg.game.actions.noop.enabled = True
        cfg.game.actions.move.enabled = True  # Enable movement

        # AOE source with presence_delta that gives shield on enter
        cfg.game.objects["buffer"] = GridObjectConfig(
            name="buffer",
            map_name="buffer",
            aoes={
                "default": AOEConfig(
                    radius=1,  # Only affects adjacent cells
                    filters=[],
                    mutations=[],  # No per-tick mutations
                    presence_deltas={"shield": 50},  # Give 50 shield on enter
                )
            },
        )

        sim = Simulation(cfg)

        # Agent is far from AOE source, should have 0 shield
        shield = sim.agent(0).inventory.get("shield", 0)
        assert shield == 0, f"Initial: expected 0 shield, got {shield}"

        # Move east (right) to get closer (still not in range)
        sim.agent(0).set_action("move_east")
        sim.step()
        shield = sim.agent(0).inventory.get("shield", 0)
        assert shield == 0, f"After move 1: expected 0 shield (not yet in range), got {shield}"

        # Move east again (still not in range, radius=1)
        sim.agent(0).set_action("move_east")
        sim.step()
        shield = sim.agent(0).inventory.get("shield", 0)
        assert shield == 0, f"After move 2: expected 0 shield (not yet in range), got {shield}"

        # Move east again (now should be in range of AOE at column 5)
        sim.agent(0).set_action("move_east")
        sim.step()
        shield = sim.agent(0).inventory.get("shield", 0)
        assert shield == 50, f"After entering AOE: expected 50 shield, got {shield}"

    def test_presence_delta_removed_on_exit(self):
        """When agent exits AOE, presence_delta should remove resources."""
        # Agent starts adjacent to buffer (within radius 1)
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "@", "S", "#"],  # Agent at col 4, Buffer at col 5 (distance=1, in range)
                ["#", "#", "#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "buffer"},
        )

        cfg.game.resource_names = ["shield"]
        cfg.game.agent.inventory.initial = {"shield": 100}
        cfg.game.agent.inventory.limits = {
            "shield": ResourceLimitsConfig(min=1000, resources=["shield"]),
        }
        # No on_tick — no passive regen
        cfg.game.actions.noop.enabled = True
        cfg.game.actions.move.enabled = True  # Enable movement

        # AOE source with presence_delta
        cfg.game.objects["buffer"] = GridObjectConfig(
            name="buffer",
            map_name="buffer",
            aoes={
                "default": AOEConfig(
                    radius=1,
                    filters=[],
                    mutations=[],
                    presence_deltas={"shield": 50},
                )
            },
        )

        sim = Simulation(cfg)

        # Agent starts in AOE (adjacent to buffer)
        # After first step, agent should have 100 + 50 = 150 shield from enter delta
        sim.agent(0).set_action("noop")
        sim.step()
        shield = sim.agent(0).inventory.get("shield", 0)
        assert shield == 150, f"After first step in AOE: expected 150 shield, got {shield}"

        # Move west (left) to exit AOE (distance will become 2, outside radius 1)
        sim.agent(0).set_action("move_west")
        sim.step()
        shield = sim.agent(0).inventory.get("shield", 0)
        # Exit delta should have removed 50 shield: 150 - 50 = 100
        assert shield == 100, f"After exiting AOE: expected 100 shield, got {shield}"


class TestAgentAOE:
    """Test agent AOE (mobile AOE with is_static=False)."""

    def test_agent_aoe_affects_other_agents(self):
        """Agent with mobile AOE should affect other agents in range."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=2, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent 0 (has AOE)
                ["#", ".", "A", ".", "#"],  # Agent 1 (in range)
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", "A": "agent.agent", ".": "empty"},
        )

        cfg.game.resource_names = ["energy"]
        cfg.game.agent.inventory.initial = {"energy": 0}
        cfg.game.agent.inventory.limits = {
            "energy": ResourceLimitsConfig(min=1000, resources=["energy"]),
        }
        # No on_tick — no passive regen
        cfg.game.actions.noop.enabled = True

        # Agent AOE - mobile AOE that gives energy to nearby agents
        cfg.game.agent.aoes = {
            "default": AOEConfig(
                radius=1,
                is_static=False,  # Mobile AOE - follows the agent
                effect_self=False,  # Don't affect self
                filters=[],
                mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 5})],
            ),
        }

        sim = Simulation(cfg)

        # Step - Agent 0's AOE should affect Agent 1
        sim.agent(0).set_action("noop")
        sim.agent(1).set_action("noop")
        sim.step()

        # Agent 1 should have received energy from Agent 0's AOE
        energy0 = sim.agent(0).inventory.get("energy", 0)
        energy1 = sim.agent(1).inventory.get("energy", 0)

        # Agent 0 should NOT have energy (effect_self=False)
        # Agent 1 should have 5 energy from Agent 0's AOE, plus 5 from their own AOE affecting Agent 0
        # Wait - both agents have the AOE, so:
        # - Agent 0's AOE affects Agent 1 (+5)
        # - Agent 1's AOE affects Agent 0 (+5)
        assert energy0 == 5, f"Agent 0 should have 5 energy from Agent 1's AOE, got {energy0}"
        assert energy1 == 5, f"Agent 1 should have 5 energy from Agent 0's AOE, got {energy1}"


class TestEffectSelf:
    """Test effect_self flag on AOE."""

    def test_effect_self_true_affects_source(self):
        """AOE with effect_self=True should affect the source object."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty"},
        )

        cfg.game.resource_names = ["energy"]
        cfg.game.agent.inventory.initial = {"energy": 0}
        cfg.game.agent.inventory.limits = {
            "energy": ResourceLimitsConfig(min=1000, resources=["energy"]),
        }
        # No on_tick — no passive regen
        cfg.game.actions.noop.enabled = True

        # Agent AOE with effect_self=True
        cfg.game.agent.aoes = {
            "default": AOEConfig(
                radius=1,
                is_static=False,
                effect_self=True,  # Affect self
                filters=[],
                mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
            ),
        }

        sim = Simulation(cfg)

        # Step
        sim.agent(0).set_action("noop")
        sim.step()

        # Agent should have energy from their own AOE
        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 10, f"Agent with effect_self=True should have 10 energy, got {energy}"

    def test_effect_self_false_does_not_affect_source(self):
        """AOE with effect_self=False should NOT affect the source object."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty"},
        )

        cfg.game.resource_names = ["energy"]
        cfg.game.agent.inventory.initial = {"energy": 0}
        cfg.game.agent.inventory.limits = {
            "energy": ResourceLimitsConfig(min=1000, resources=["energy"]),
        }
        # No on_tick — no passive regen
        cfg.game.actions.noop.enabled = True

        # Agent AOE with effect_self=False
        cfg.game.agent.aoes = {
            "default": AOEConfig(
                radius=1,
                is_static=False,
                effect_self=False,  # Don't affect self
                filters=[],
                mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
            ),
        }

        sim = Simulation(cfg)

        # Step
        sim.agent(0).set_action("noop")
        sim.step()

        # Agent should NOT have energy (no other targets in range and effect_self=False)
        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 0, f"Agent with effect_self=False should have 0 energy, got {energy}"


class TestMobileVsStatic:
    """Test the difference between mobile (is_static=False) and static (is_static=True) AOE."""

    def test_static_aoe_on_grid_object(self):
        """Grid object with static AOE should have effects registered at fixed cells."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent in range
                ["#", ".", "S", ".", "#"],  # Static AOE source
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "beacon"},
        )

        cfg.game.resource_names = ["energy"]
        cfg.game.agent.inventory.initial = {"energy": 0}
        cfg.game.agent.inventory.limits = {
            "energy": ResourceLimitsConfig(min=1000, resources=["energy"]),
        }
        # No on_tick — no passive regen
        cfg.game.actions.noop.enabled = True

        # Static AOE source (default is_static=True)
        cfg.game.objects["beacon"] = GridObjectConfig(
            name="beacon",
            map_name="beacon",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    is_static=True,  # Explicit static (default)
                    filters=[],
                    mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
                )
            },
        )

        sim = Simulation(cfg)

        # Step
        sim.agent(0).set_action("noop")
        sim.step()

        # Agent should have received energy
        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 10, f"Agent in range of static AOE should have 10 energy, got {energy}"
