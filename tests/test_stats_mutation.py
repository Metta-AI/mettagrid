"""Tests for StatsMutation end-to-end in C++ simulation.

These tests verify that:
1. StatsMutation correctly sets stats in the C++ simulation
2. Stats are properly accumulated via self-referencing SumGameValue
3. Different StatsTarget values (game, agent) work correctly
"""

from mettagrid.config.game_value import SumGameValue, inv, stat, val
from mettagrid.config.handler_config import AOEConfig
from mettagrid.config.mettagrid_config import (
    GridObjectConfig,
    MettaGridConfig,
    ResourceLimitsConfig,
)
from mettagrid.config.mutation import (
    StatsMutation,
    StatsTarget,
    logStat,
)
from mettagrid.simulator import Simulation


class TestStatsMutationClass:
    """Test StatsMutation class attributes."""

    def test_stats_mutation_class(self):
        """StatsMutation should have correct attributes."""
        m = StatsMutation(stat="hits", source=val(1), target=StatsTarget.GAME)
        assert m.mutation_type == "stats"
        assert m.stat == "hits"
        assert m.source == val(1)
        assert m.target == StatsTarget.GAME

    def test_stats_mutation_defaults(self):
        """StatsMutation should have sensible defaults."""
        m = StatsMutation(stat="count", source=val(0))
        assert m.target == StatsTarget.GAME

    def test_stats_mutation_source_is_required(self):
        """StatsMutation requires source field."""
        m = StatsMutation(stat="x", source=inv("gold"))
        assert m.source == inv("gold")


class TestStatsMutationHelper:
    """Test logStat() helper function."""

    def test_log_stat_helper(self):
        """logStat() should create a StatsMutation with accumulation source."""
        m = logStat("events")
        assert isinstance(m, StatsMutation)
        assert m.stat == "events"
        assert m.source == SumGameValue(values=[stat("game.events"), val(1)])
        assert m.target == StatsTarget.GAME

    def test_log_stat_helper_with_delta(self):
        """logStat() should wrap delta in SumGameValue for accumulation."""
        m = logStat("damage", delta=50)
        assert m.stat == "damage"
        assert m.source == SumGameValue(values=[stat("game.damage"), val(50)])

    def test_log_stat_helper_with_target(self):
        """logStat() should accept target parameter."""
        m = logStat("global_events", target=StatsTarget.GAME)
        assert m.target == StatsTarget.GAME

    def test_log_stat_helper_agent_target(self):
        """logStat() with agent target should use agent-scoped self-reference."""
        m = logStat("hits", target=StatsTarget.AGENT)
        assert m.source == SumGameValue(values=[stat("hits"), val(1)])

    def test_log_stat_helper_with_source(self):
        """logStat() with source should wrap source in SumGameValue."""
        m = logStat("gold_total", source=inv("gold"))
        assert m.source == SumGameValue(values=[stat("game.gold_total"), inv("gold")])


class TestStatsMutationEndToEnd:
    """End-to-end tests verifying StatsMutation works in C++ simulation."""

    def test_aoe_stats_mutation_logs_game_stat(self):
        """AOE handler with logStat mutation should log to game stats."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent
                ["#", ".", "S", ".", "#"],  # AOE source that logs stats
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "counter"},
        )

        cfg.game.actions.noop.enabled = True

        # AOE source that logs "aoe_hits" to game stats
        cfg.game.objects["counter"] = GridObjectConfig(
            name="counter",
            map_name="counter",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[],
                    mutations=[logStat("aoe_hits", target=StatsTarget.GAME)],
                )
            },
        )

        sim = Simulation(cfg)

        # Get initial game stats
        initial_stats = sim.episode_stats["game"]
        initial_hits = initial_stats.get("aoe_hits", 0)

        # Step simulation - AOE should fire and log stat
        sim.agent(0).set_action("noop")
        sim.step()

        # Check game stats increased
        final_stats = sim.episode_stats["game"]
        final_hits = final_stats.get("aoe_hits", 0)

        assert final_hits == initial_hits + 1, f"Game stat 'aoe_hits' should increase by 1, got {final_hits}"

    def test_stats_mutation_accumulates_over_steps(self):
        """Stats should accumulate across multiple steps."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],  # Agent
                ["#", ".", "S", ".", "#"],  # AOE source
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "counter"},
        )

        cfg.game.actions.noop.enabled = True

        cfg.game.objects["counter"] = GridObjectConfig(
            name="counter",
            map_name="counter",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[],
                    mutations=[logStat("ticks", delta=5, target=StatsTarget.GAME)],
                )
            },
        )

        sim = Simulation(cfg)

        # Run 3 steps
        for _ in range(3):
            sim.agent(0).set_action("noop")
            sim.step()

        # Check game stats - should be 3 * 5 = 15
        stats = sim.episode_stats["game"]
        ticks = stats.get("ticks", 0)

        assert ticks == 15, f"Game stat 'ticks' should be 15 after 3 steps with delta=5, got {ticks}"

    def test_source_inv_logs_inventory_count(self):
        """StatsMutation with source=inv("gold") accumulates the agent's gold count."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],
                ["#", ".", "S", ".", "#"],
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "counter"},
        )

        cfg.game.resource_names = ["gold"]
        cfg.game.agent.inventory.initial = {"gold": 42}
        cfg.game.agent.inventory.limits = {"resources": ResourceLimitsConfig(resources=["gold"])}
        cfg.game.actions.noop.enabled = True

        cfg.game.objects["counter"] = GridObjectConfig(
            name="counter",
            map_name="counter",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[],
                    mutations=[logStat("gold_count", source=inv("gold"), target=StatsTarget.GAME)],
                )
            },
        )

        sim = Simulation(cfg)
        sim.agent(0).set_action("noop")
        sim.step()

        stats = sim.episode_stats["game"]
        assert stats.get("gold_count", 0) == 42, f"Expected gold_count=42, got {stats.get('gold_count', 0)}"
