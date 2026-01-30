from mettagrid.config.filter.filter import HandlerTarget
from mettagrid.config.filter.vibe_filter import VibeFilter
from mettagrid.config.handler_config import Handler
from mettagrid.config.mettagrid_config import MettaGridConfig, ResourceLimitsConfig
from mettagrid.config.mutation.mutation import EntityTarget
from mettagrid.config.mutation.resource_mutation import ResourceDeltaMutation
from mettagrid.simulator import Action, Simulation


class TestVibeDependentRegeneration:
    """Test vibe-dependent inventory regeneration functionality."""

    def test_vibe_dependent_regen_different_rates(self):
        """Test that different vibes regenerate resources at different rates."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#"],
                ["#", "@", "#"],
                ["#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty"},
        )

        cfg.game.resource_names = ["energy"]
        # Different regen rates for different vibes
        cfg.game.agent.on_tick = {
            "regen_default": Handler(
                filters=[VibeFilter(target=HandlerTarget.ACTOR, vibe="default")],
                mutations=[ResourceDeltaMutation(target=EntityTarget.ACTOR, deltas={"energy": 2})],
            ),
            "regen_charger": Handler(
                filters=[VibeFilter(target=HandlerTarget.ACTOR, vibe="charger")],
                mutations=[ResourceDeltaMutation(target=EntityTarget.ACTOR, deltas={"energy": 10})],
            ),
        }
        cfg.game.agent.inventory.initial = {"energy": 0}
        cfg.game.actions.noop.enabled = True
        cfg.game.actions.change_vibe.enabled = True

        sim = Simulation(cfg)

        # Step 1: Default vibe - should regenerate 2 energy
        sim.agent(0).set_action(Action(name="noop"))
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 2, f"With default vibe, energy should regenerate to 2, got {energy}"

        # Step 2: Change to charger vibe
        sim.agent(0).set_action("change_vibe_charger")
        sim.step()

        # After changing vibe, regen happens with new vibe rate
        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 12, f"With charger vibe, energy should regenerate by 10 (2+10=12), got {energy}"

        # Step 3: Stay on charger vibe - should continue regenerating at 10/step
        sim.agent(0).set_action(Action(name="noop"))
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 22, f"With charger vibe, energy should be 22 (12+10), got {energy}"

        # Step 4: Change back to default vibe
        sim.agent(0).set_action("change_vibe_default")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 24, f"With default vibe, energy should be 24 (22+2), got {energy}"

    def test_vibe_dependent_regen_no_filter_acts_as_fallback(self):
        """Test that a handler with no VibeFilter runs for all vibes (fallback behavior)."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#"],
                ["#", "@", "#"],
                ["#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty"},
        )

        cfg.game.resource_names = ["energy"]
        # No VibeFilter means it runs for ALL vibes
        cfg.game.agent.on_tick = {
            "regen": Handler(
                mutations=[ResourceDeltaMutation(target=EntityTarget.ACTOR, deltas={"energy": 5})],
            ),
        }
        cfg.game.agent.inventory.initial = {"energy": 0}
        cfg.game.actions.noop.enabled = True
        cfg.game.actions.change_vibe.enabled = True

        sim = Simulation(cfg)

        # Step 1: Default vibe - should regenerate 5 energy
        sim.agent(0).set_action(Action(name="noop"))
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 5, f"With default vibe, energy should be 5, got {energy}"

        # Step 2: Change to charger vibe - handler has no filter, still runs
        sim.agent(0).set_action("change_vibe_charger")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 10, f"With charger vibe (no filter), energy should be 10 (5+5), got {energy}"

        # Step 3: Change to another vibe - still runs
        sim.agent(0).set_action("change_vibe_carbon_a")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 15, f"With carbon_a vibe (no filter), energy should be 15 (10+5), got {energy}"

    def test_vibe_dependent_regen_no_matching_handler(self):
        """Test that vibes without a matching handler get no regen."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#"],
                ["#", "@", "#"],
                ["#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty"},
        )

        cfg.game.resource_names = ["energy"]
        # Only configure charger vibe - no handler for default
        cfg.game.agent.on_tick = {
            "regen_charger": Handler(
                filters=[VibeFilter(target=HandlerTarget.ACTOR, vibe="charger")],
                mutations=[ResourceDeltaMutation(target=EntityTarget.ACTOR, deltas={"energy": 10})],
            ),
        }
        cfg.game.agent.inventory.initial = {"energy": 0}
        cfg.game.actions.noop.enabled = True
        cfg.game.actions.change_vibe.enabled = True

        sim = Simulation(cfg)

        # Step 1: Default vibe (no matching handler) - no regeneration
        sim.agent(0).set_action(Action(name="noop"))
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 0, f"Unconfigured default vibe should not regenerate, got {energy}"

        # Step 2: Change to charger vibe - should regenerate
        sim.agent(0).set_action("change_vibe_charger")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 10, f"Charger vibe should regenerate 10, got {energy}"

        # Step 3: Change back to default - no regeneration
        sim.agent(0).set_action("change_vibe_default")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 10, f"Default vibe should not regenerate (still 10), got {energy}"


class TestNegativeRegeneration:
    """Test negative inventory regeneration (decay) functionality."""

    def test_negative_regen_decreases_resource(self):
        """Test that negative regen values decrease resources over time."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#"],
                ["#", "@", "#"],
                ["#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty"},
        )

        cfg.game.resource_names = ["energy"]
        cfg.game.agent.on_tick = {
            "decay": Handler(
                mutations=[ResourceDeltaMutation(target=EntityTarget.ACTOR, deltas={"energy": -3})],
            ),
        }
        cfg.game.agent.inventory.initial = {"energy": 20}
        cfg.game.actions.noop.enabled = True

        sim = Simulation(cfg)

        # Step 1: Energy should decrease by 3
        sim.agent(0).set_action(Action(name="noop"))
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 17, f"Energy should decay to 17, got {energy}"

        # Step 2: Energy should decrease again
        sim.agent(0).set_action(Action(name="noop"))
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 14, f"Energy should decay to 14, got {energy}"

        # Step 3: Energy should decrease again
        sim.agent(0).set_action(Action(name="noop"))
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 11, f"Energy should decay to 11, got {energy}"

    def test_negative_regen_floors_at_zero(self):
        """Test that negative regen doesn't go below zero."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#"],
                ["#", "@", "#"],
                ["#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty"},
        )

        cfg.game.resource_names = ["energy"]
        cfg.game.agent.on_tick = {
            "decay": Handler(
                mutations=[ResourceDeltaMutation(target=EntityTarget.ACTOR, deltas={"energy": -10})],
            ),
        }
        cfg.game.agent.inventory.initial = {"energy": 5}
        cfg.game.actions.noop.enabled = True

        sim = Simulation(cfg)

        # Step 1: Energy should decay to 0 (not -5)
        sim.agent(0).set_action(Action(name="noop"))
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 0, f"Energy should floor at 0, got {energy}"

        # Step 2: Energy should stay at 0
        sim.agent(0).set_action(Action(name="noop"))
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 0, f"Energy should remain at 0, got {energy}"

    def test_vibe_dependent_negative_regen(self):
        """Test that different vibes can have different decay rates."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#"],
                ["#", "@", "#"],
                ["#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty"},
        )

        cfg.game.resource_names = ["energy"]
        cfg.game.agent.on_tick = {
            "decay_default": Handler(
                filters=[VibeFilter(target=HandlerTarget.ACTOR, vibe="default")],
                mutations=[ResourceDeltaMutation(target=EntityTarget.ACTOR, deltas={"energy": -2})],
            ),
            "regen_charger": Handler(
                filters=[VibeFilter(target=HandlerTarget.ACTOR, vibe="charger")],
                mutations=[ResourceDeltaMutation(target=EntityTarget.ACTOR, deltas={"energy": 5})],
            ),
        }
        cfg.game.agent.inventory.initial = {"energy": 20}
        cfg.game.actions.noop.enabled = True
        cfg.game.actions.change_vibe.enabled = True

        sim = Simulation(cfg)

        # Step 1: Default vibe - should decay by 2
        sim.agent(0).set_action(Action(name="noop"))
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 18, f"With default vibe, energy should decay to 18, got {energy}"

        # Step 2: Change to charger vibe - should regenerate
        sim.agent(0).set_action("change_vibe_charger")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 23, f"With charger vibe, energy should increase to 23 (18+5), got {energy}"

        # Step 3: Change back to default - should decay again
        sim.agent(0).set_action("change_vibe_default")
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 21, f"With default vibe, energy should decay to 21 (23-2), got {energy}"


class TestInventoryRegeneration:
    """Test inventory regeneration functionality."""

    def test_energy_regeneration_basic(self):
        """Test that energy regenerates every tick with on_tick."""
        # Create a simple environment with energy regeneration
        cfg = MettaGridConfig.EmptyRoom(num_agents=2, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#"],
                ["#", "@", "@", "#"],
                ["#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty"},
        )

        # Add energy to resources and configure regeneration
        cfg.game.resource_names = ["energy", "heart", "battery_blue"]
        cfg.game.agent.on_tick = {
            "regen": Handler(
                mutations=[ResourceDeltaMutation(target=EntityTarget.ACTOR, deltas={"energy": 5})],
            ),
        }
        cfg.game.agent.inventory.initial = {"energy": 10}  # Start with 10 energy
        cfg.game.actions.noop.enabled = True

        sim = Simulation(cfg)

        # Get initial energy levels
        grid_objects = sim.grid_objects()
        agents = []
        for _obj_id, obj in grid_objects.items():
            if "agent_id" in obj:  # This is an agent
                agents.append(obj)

        assert len(agents) == 2, "Should find 2 agents"

        # Check initial energy
        energy_idx = sim.resource_names.index("energy")
        for agent in agents:
            assert agent["inventory"][energy_idx] == 10, "Each agent should start with 10 energy"

        # on_tick run every step, so energy increases by 5 each step
        for i in range(sim.num_agents):
            sim.agent(i).set_action(Action(name="noop"))
        sim.step()

        for i in range(sim.num_agents):
            energy = sim.agent(i).inventory.get("energy", 0)
            assert energy == 15, f"Agent {i} energy should be 15 at step 1, got {energy}"

        # Step 2
        for i in range(sim.num_agents):
            sim.agent(i).set_action(Action(name="noop"))
        sim.step()

        for i in range(sim.num_agents):
            energy = sim.agent(i).inventory.get("energy", 0)
            assert energy == 20, f"Agent {i} energy should be 20 at step 2, got {energy}"

        # Step 3
        for i in range(sim.num_agents):
            sim.agent(i).set_action(Action(name="noop"))
        sim.step()

        for i in range(sim.num_agents):
            energy = sim.agent(i).inventory.get("energy", 0)
            assert energy == 25, f"Agent {i} energy should be 25 at step 3, got {energy}"

    def test_regeneration_disabled_no_handlers(self):
        """Test that regeneration is disabled when no on_tick are set."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#"],
                ["#", "@", "#"],
                ["#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty"},
        )

        cfg.game.resource_names = ["energy"]
        # No on_tick set — regen disabled
        cfg.game.agent.inventory.initial = {"energy": 10}
        cfg.game.actions.noop.enabled = True

        sim = Simulation(cfg)

        # Take many steps
        for _ in range(10):
            sim.agent(0).set_action(Action(name="noop"))
            sim.step()
            energy = sim.agent(0).inventory.get("energy", 0)
            assert energy == 10, f"Energy should not regenerate with no handlers, got {energy}"

    def test_regeneration_with_resource_limits(self):
        """Test that regeneration respects resource limits."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#"],
                ["#", "@", "#"],
                ["#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty"},
        )

        cfg.game.resource_names = ["energy"]
        cfg.game.agent.on_tick = {
            "regen": Handler(
                mutations=[ResourceDeltaMutation(target=EntityTarget.ACTOR, deltas={"energy": 10})],
            ),
        }
        cfg.game.agent.inventory.initial = {"energy": 95}
        cfg.game.agent.inventory.limits = {
            "energy": ResourceLimitsConfig(min=100, resources=["energy"]),  # Max 100 energy
        }
        cfg.game.actions.noop.enabled = True

        sim = Simulation(cfg)

        # Take a step - should regenerate but cap at 100
        sim.agent(0).set_action(Action(name="noop"))
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 100, f"Energy should cap at 100 (limit), got {energy}"

        # Take another step - should stay at 100
        sim.agent(0).set_action(Action(name="noop"))
        sim.step()

        energy = sim.agent(0).inventory.get("energy", 0)
        assert energy == 100, f"Energy should remain at 100, got {energy}"
