from mettagrid.config.handler_config import Handler, withdraw
from mettagrid.config.mettagrid_config import GridObjectConfig, InventoryConfig, MettaGridConfig, ResourceLimitsConfig
from mettagrid.simulator import Simulation


class TestGridObjectInventory:
    """Test grid object inventory and handler functionality."""

    def test_object_removed_from_grid_when_emptied(self):
        """Test that a chest with remove_when_empty withdraw is removed from grid when depleted."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True)

        cfg.game.resource_names = ["gold"]
        cfg.game.agent.inventory.initial = {}

        cfg.game.objects["extractor"] = GridObjectConfig(
            name="extractor",
            on_use_handlers={
                "extract": Handler(
                    mutations=[withdraw({"gold": 5}, remove_when_empty=True)],
                ),
            },
            inventory=InventoryConfig(
                initial={"gold": 5},
                limits={"gold": ResourceLimitsConfig(min=100, resources=["gold"])},
            ),
        )

        cfg = cfg.with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "E", ".", "#"],
                ["#", ".", "@", ".", "#"],
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "E": "extractor"},
        )

        cfg.game.actions.move.enabled = True

        sim = Simulation(cfg)
        gold_idx = sim.resource_names.index("gold")

        # Verify extractor exists on grid
        grid_objects = sim.grid_objects()
        extractors = [obj for obj in grid_objects.values() if obj["type_name"] == "extractor"]
        assert len(extractors) == 1, f"Expected 1 extractor, found {len(extractors)}"

        # Move north into extractor to trigger withdraw
        sim.agent(0).set_action("move_north")
        sim.step()

        # Check agent got the gold
        grid_objects_after = sim.grid_objects()
        agent = next(obj for obj in grid_objects_after.values() if "agent_id" in obj)
        assert agent["inventory"].get(gold_idx, 0) == 5, (
            f"Agent should have 5 gold, has {agent['inventory'].get(gold_idx, 0)}"
        )

        # Extractor should be removed from the grid
        extractors_after = [obj for obj in grid_objects_after.values() if obj["type_name"] == "extractor"]
        assert len(extractors_after) == 0, (
            f"Extractor should be removed from grid after depletion, but found {len(extractors_after)}"
        )
