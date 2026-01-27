"""Test collective (shared inventory) functionality for mettagrid."""

from mettagrid.config.mettagrid_c_config import convert_to_cpp_game_config
from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    AssemblerConfig,
    ChestConfig,
    CollectiveConfig,
    GameConfig,
    InventoryConfig,
    MettaGridConfig,
    MoveActionConfig,
    NoopActionConfig,
    ProtocolConfig,
    ResourceLimitsConfig,
    WallConfig,
)
from mettagrid.map_builder.ascii import AsciiMapBuilder
from mettagrid.mapgen.utils.ascii_grid import DEFAULT_CHAR_TO_NAME
from mettagrid.simulator import Simulation


class TestCollectiveConfig:
    """Test CollectiveConfig creation and conversion."""

    def test_collective_config_basic(self):
        """Test that CollectiveConfig can be created with basic fields."""
        cfg = CollectiveConfig(
            name="shared_storage",
            inventory=InventoryConfig(
                initial={"gold": 100},
                limits={"gold": ResourceLimitsConfig(min=1000, resources=["gold"])},
            ),
        )
        assert cfg.name == "shared_storage"
        assert cfg.inventory.initial["gold"] == 100

    def test_collective_field_set(self):
        """Test that collective field is set on the config."""
        cfg = WallConfig(name="my_wall", collective="shared")
        assert cfg.collective == "shared"

    def test_game_config_with_collectives(self):
        """Test that GameConfig accepts collectives dict."""
        game_config = GameConfig(
            num_agents=1,
            collectives={
                "team_storage": CollectiveConfig(inventory=InventoryConfig(initial={"gold": 50})),
            },
            resource_names=["gold"],
        )
        assert len(game_config.collectives) == 1
        assert "team_storage" in game_config.collectives


class TestCollectiveConversion:
    """Test Python to C++ collective conversion."""

    def test_collective_cpp_conversion(self):
        """Test that collective configs are properly converted to C++."""
        game_config = GameConfig(
            num_agents=1,
            resource_names=["gold", "silver"],
            collectives={
                "vault": CollectiveConfig(
                    inventory=InventoryConfig(
                        initial={"gold": 100, "silver": 50},
                        limits={"precious": ResourceLimitsConfig(min=500, resources=["gold", "silver"])},
                    ),
                ),
            },
        )

        cpp_config = convert_to_cpp_game_config(game_config)

        # Check that collective was converted
        assert "vault" in cpp_config.collectives
        vault_config = cpp_config.collectives["vault"]
        assert vault_config.name == "vault"

        # Check initial inventory was converted (resource IDs, not names)
        gold_id = game_config.resource_names.index("gold")
        silver_id = game_config.resource_names.index("silver")
        assert vault_config.initial_inventory[gold_id] == 100
        assert vault_config.initial_inventory[silver_id] == 50


class TestCollectiveIntegration:
    """Test collective integration with the simulation."""

    def test_collective_with_objects(self):
        """Test that objects can be associated with a collective."""
        cfg = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                max_steps=100,
                resource_names=["gold"],
                actions=ActionsConfig(noop=NoopActionConfig(), move=MoveActionConfig()),
                collectives={
                    "team_vault": CollectiveConfig(
                        inventory=InventoryConfig(
                            initial={"gold": 100},
                            limits={"gold": ResourceLimitsConfig(min=1000, resources=["gold"])},
                        ),
                    ),
                },
                objects={
                    "wall": WallConfig(),
                    "chest": ChestConfig(
                        name="team_chest",
                        collective="team_vault",  # Associate with collective
                        vibe_transfers={"up": {"gold": -10}},  # withdraw 10 gold
                    ),
                },
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        ["#", "#", "#", "#", "#"],
                        ["#", ".", ".", ".", "#"],
                        ["#", ".", "C", ".", "#"],
                        ["#", ".", "@", ".", "#"],
                        ["#", "#", "#", "#", "#"],
                    ],
                    char_to_map_name={
                        "#": "wall",
                        "@": "agent.agent",
                        ".": "empty",
                        "C": "team_chest",
                    },
                ),
            )
        )

        # Verify collective is set on chest
        assert cfg.game.objects["chest"].collective == "team_vault"

        # Create simulation - this verifies the C++ side accepts our config
        sim = Simulation(cfg)
        assert sim is not None

        # The simulation should start successfully
        obs = sim._c_sim.observations()
        assert obs is not None

    def test_multiple_collectives(self):
        """Test that multiple collectives can be configured."""
        game_config = GameConfig(
            num_agents=2,
            resource_names=["gold", "silver"],
            collectives={
                "team_red_vault": CollectiveConfig(inventory=InventoryConfig(initial={"gold": 50})),
                "team_blue_vault": CollectiveConfig(inventory=InventoryConfig(initial={"silver": 50})),
            },
        )

        cpp_config = convert_to_cpp_game_config(game_config)

        assert len(cpp_config.collectives) == 2
        assert "team_red_vault" in cpp_config.collectives
        assert "team_blue_vault" in cpp_config.collectives

    def test_collective_with_assembler(self):
        """Test that assemblers can be associated with a collective."""
        cfg = MettaGridConfig(
            game=GameConfig(
                num_agents=1,
                max_steps=100,
                resource_names=["ore", "metal"],
                actions=ActionsConfig(noop=NoopActionConfig(), move=MoveActionConfig()),
                collectives={
                    "factory_storage": CollectiveConfig(
                        inventory=InventoryConfig(initial={"ore": 100}),
                    ),
                },
                objects={
                    "wall": WallConfig(),
                    "smelter": AssemblerConfig(
                        name="smelter",
                        collective="factory_storage",
                        protocols=[
                            ProtocolConfig(input_resources={"ore": 1}, output_resources={"metal": 1}, cooldown=5)
                        ],
                    ),
                },
                map_builder=AsciiMapBuilder.Config(
                    map_data=[
                        ["#", "#", "#"],
                        ["#", "@", "#"],
                        ["#", "#", "#"],
                    ],
                    char_to_map_name=DEFAULT_CHAR_TO_NAME,
                ),
            )
        )

        # Verify collective is set on assembler
        assert cfg.game.objects["smelter"].collective == "factory_storage"

        # Create simulation
        sim = Simulation(cfg)
        assert sim is not None


class TestCollectiveIdMapping:
    """Test that collective IDs are properly assigned during conversion."""

    def test_collective_field_on_object(self):
        """Test that collective field is properly set on objects."""
        game_config = GameConfig(
            num_agents=1,
            resource_names=["gold"],
            collectives={"vault": CollectiveConfig(inventory=InventoryConfig())},
            objects={
                "wall": WallConfig(collective="vault"),
            },
        )

        # Verify the Python config has the collective set
        assert game_config.objects["wall"].collective == "vault"

        # C++ conversion should succeed (actual collective_id assignment is tested via AOE tests)
        cpp_config = convert_to_cpp_game_config(game_config)
        assert cpp_config is not None

    def test_multiple_objects_same_collective(self):
        """Test that multiple objects can have the same collective."""
        game_config = GameConfig(
            num_agents=1,
            resource_names=["gold"],
            collectives={"shared": CollectiveConfig(inventory=InventoryConfig())},
            objects={
                "wall1": WallConfig(name="wall1", collective="shared"),
                "wall2": WallConfig(name="wall2", collective="shared"),
            },
        )

        # Both walls should have the same collective
        assert game_config.objects["wall1"].collective == "shared"
        assert game_config.objects["wall2"].collective == "shared"

        # C++ conversion should succeed
        cpp_config = convert_to_cpp_game_config(game_config)
        assert cpp_config is not None
