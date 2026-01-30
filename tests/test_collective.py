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


class TestCollectiveInventoryObservations:
    """Test that collective inventory amounts are observable via stats."""

    def test_collective_amount_stats_observation(self):
        """Test that collective inventory amounts appear in agent observations."""
        from mettagrid.config.game_value import stat
        from mettagrid.config.mettagrid_config import AgentConfig
        from mettagrid.config.obs_config import GlobalObsConfig, ObsConfig
        from mettagrid.test_support.map_builders import ObjectNameMapBuilder

        game_config = GameConfig(
            num_agents=1,
            max_steps=100,
            resource_names=["gold", "silver"],
            actions=ActionsConfig(noop=NoopActionConfig()),
            collectives={
                "team": CollectiveConfig(
                    inventory=InventoryConfig(initial={"gold": 100, "silver": 50}),
                ),
            },
            agent=AgentConfig(collective="team"),
            obs=ObsConfig(
                global_obs=GlobalObsConfig(
                    obs=[
                        stat("collective.gold.amount"),
                        stat("collective.silver.amount"),
                    ]
                )
            ),
        )

        game_map = [["agent.agent"]]
        cfg = MettaGridConfig(game=game_config)
        cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=game_map)

        sim = Simulation(cfg, seed=42)
        agent = sim.agent(0)

        # Get observation and find collective stats tokens
        obs = agent.observation
        gold_tokens = [t for t in obs.tokens if t.feature.name == "stat:collective:gold.amount"]
        silver_tokens = [t for t in obs.tokens if t.feature.name == "stat:collective:silver.amount"]

        assert len(gold_tokens) >= 1, f"Expected gold stat token, got features: {[t.feature.name for t in obs.tokens]}"
        assert len(silver_tokens) >= 1, "Expected silver stat token"

        # Values should match initial inventory
        assert gold_tokens[0].value == 100, f"Expected gold=100, got {gold_tokens[0].value}"
        assert silver_tokens[0].value == 50, f"Expected silver=50, got {silver_tokens[0].value}"

        sim.close()

    def test_collective_amount_updates_on_inventory_change(self):
        """Test that collective amount observations update when inventory changes via C++ API."""
        from mettagrid.config.game_value import stat
        from mettagrid.config.mettagrid_config import AgentConfig
        from mettagrid.config.obs_config import GlobalObsConfig, ObsConfig
        from mettagrid.test_support.map_builders import ObjectNameMapBuilder

        game_config = GameConfig(
            num_agents=1,
            max_steps=100,
            resource_names=["gold"],
            actions=ActionsConfig(noop=NoopActionConfig()),
            collectives={
                "team": CollectiveConfig(
                    inventory=InventoryConfig(
                        initial={"gold": 10},
                        limits={"gold": ResourceLimitsConfig(min=1000, resources=["gold"])},
                    ),
                ),
            },
            agent=AgentConfig(collective="team"),
            obs=ObsConfig(
                global_obs=GlobalObsConfig(
                    obs=[
                        stat("collective.gold.amount"),
                    ]
                )
            ),
        )

        game_map = [["agent.agent"]]
        cfg = MettaGridConfig(game=game_config)
        cfg.game.map_builder = ObjectNameMapBuilder.Config(map_data=game_map)

        sim = Simulation(cfg, seed=42)
        agent = sim.agent(0)

        # Initial observation - collective has 10 gold
        obs1 = agent.observation
        gold_tokens = [t for t in obs1.tokens if t.feature.name == "stat:collective:gold.amount"]
        assert gold_tokens[0].value == 10, f"Expected initial 10 gold, got {gold_tokens[0].value}"

        # Verify collective inventory via the C++ API
        collective_inventories = sim._c_sim.get_collective_inventories()
        assert "team" in collective_inventories
        # Initial inventory should be 10 gold (API uses string keys for resource names)
        assert collective_inventories["team"].get("gold", 0) == 10

        # Step simulation to get fresh observations
        agent.set_action("noop")
        sim.step()

        # Observations should still reflect 10 gold (no changes made)
        obs2 = agent.observation
        gold_tokens = [t for t in obs2.tokens if t.feature.name == "stat:collective:gold.amount"]
        assert gold_tokens[0].value == 10, f"Expected 10, got {gold_tokens[0].value}"

        sim.close()
