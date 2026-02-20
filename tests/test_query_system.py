"""Tests for the QuerySystem (MaterializedQuery + ClosureQuery).

These tests verify that:
1. Materialized queries are computed correctly via BFS from roots through bridges
2. Disconnected components don't receive the materialized tag
3. Diagonal adjacency works (8-connected, radius=1)
4. No roots means no materialized tag applied
5. Custom bridge radius expands through gaps
6. Multiple independent materialized queries work simultaneously
"""

from mettagrid.config.filter import HandlerTarget, TagFilter
from mettagrid.config.mettagrid_config import (
    GridObjectConfig,
    MettaGridConfig,
)
from mettagrid.config.query import ClosureQuery, MaterializedQuery, Query
from mettagrid.config.tag import typeTag
from mettagrid.simulator import Simulation


def _make_tag_checker(sim, cfg):
    """Return a helper that checks if an object at (r, c) has a given tag."""
    id_map = cfg.game.id_map()
    tag_names = id_map.tag_names()
    tag_name_to_id = {name: idx for idx, name in enumerate(tag_names)}

    def has_tag(tag_name, row, col):
        objects = sim._c_sim.grid_objects()
        for _obj_id, obj_data in objects.items():
            if obj_data["r"] == row and obj_data["c"] == col:
                return obj_data["has_tag"](tag_name_to_id[tag_name])
        return False

    return has_tag


class TestBasicClosure:
    """Test basic closure tag computation via MaterializedQuery."""

    def test_hub_and_adjacent_wires_get_closure_tag(self):
        """Hub (root) + adjacent wires (bridge) should all get the closure tag."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", ".", ".", "#"],
                ["#", ".", "W", "H", "W", ".", "#"],
                ["#", ".", ".", "W", ".", ".", "#"],
                ["#", ".", ".", "@", ".", ".", "#"],
                ["#", "#", "#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "H": "hub", "W": "wire"},
        )
        cfg.game.actions.noop.enabled = True

        cfg.game.objects["hub"] = GridObjectConfig(
            name="hub",
            map_name="hub",
            tags=[typeTag("hub")],
        )
        cfg.game.objects["wire"] = GridObjectConfig(
            name="wire",
            map_name="wire",
            tags=[typeTag("wire")],
        )

        cfg.game.materialize_queries = [
            MaterializedQuery(
                tag="connected",
                query=ClosureQuery(
                    source=typeTag("hub"),
                    bridge=[TagFilter(target=HandlerTarget.TARGET, tag=typeTag("wire"))],
                    radius=1,
                ),
            ),
        ]

        sim = Simulation(cfg)
        has_tag = _make_tag_checker(sim, cfg)

        assert has_tag("connected", 2, 3), "Hub should have 'connected' tag"
        assert has_tag("connected", 2, 2), "Wire left of hub should have 'connected' tag"
        assert has_tag("connected", 2, 4), "Wire right of hub should have 'connected' tag"
        assert has_tag("connected", 3, 3), "Wire below hub should have 'connected' tag"

    def test_disconnected_wire_not_tagged(self):
        """Wire not connected to hub should NOT get the closure tag."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", ".", ".", "#"],
                ["#", ".", "H", "W", ".", "W", "#"],
                ["#", ".", ".", ".", ".", ".", "#"],
                ["#", ".", ".", "@", ".", ".", "#"],
                ["#", "#", "#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "H": "hub", "W": "wire"},
        )
        cfg.game.actions.noop.enabled = True

        cfg.game.objects["hub"] = GridObjectConfig(
            name="hub",
            map_name="hub",
            tags=[typeTag("hub")],
        )
        cfg.game.objects["wire"] = GridObjectConfig(
            name="wire",
            map_name="wire",
            tags=[typeTag("wire")],
        )

        cfg.game.materialize_queries = [
            MaterializedQuery(
                tag="connected",
                query=ClosureQuery(
                    source=typeTag("hub"),
                    bridge=[TagFilter(target=HandlerTarget.TARGET, tag=typeTag("wire"))],
                    radius=1,
                ),
            ),
        ]

        sim = Simulation(cfg)
        has_tag = _make_tag_checker(sim, cfg)

        assert has_tag("connected", 2, 3), "Wire next to hub should have 'connected' tag"
        assert not has_tag("connected", 2, 5), "Disconnected wire should NOT have 'connected' tag"

    def test_diagonal_adjacency(self):
        """Wire diagonally adjacent to hub should get tagged (8-connected, radius=1)."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", ".", "#"],
                ["#", ".", "H", ".", ".", "#"],
                ["#", ".", ".", "W", ".", "#"],
                ["#", ".", ".", ".", "@", "#"],
                ["#", "#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "H": "hub", "W": "wire"},
        )
        cfg.game.actions.noop.enabled = True

        cfg.game.objects["hub"] = GridObjectConfig(
            name="hub",
            map_name="hub",
            tags=[typeTag("hub")],
        )
        cfg.game.objects["wire"] = GridObjectConfig(
            name="wire",
            map_name="wire",
            tags=[typeTag("wire")],
        )

        cfg.game.materialize_queries = [
            MaterializedQuery(
                tag="connected",
                query=ClosureQuery(
                    source=typeTag("hub"),
                    bridge=[TagFilter(target=HandlerTarget.TARGET, tag=typeTag("wire"))],
                    radius=1,
                ),
            ),
        ]

        sim = Simulation(cfg)
        has_tag = _make_tag_checker(sim, cfg)

        assert has_tag("connected", 2, 2), "Hub should have 'connected' tag"
        assert has_tag("connected", 3, 3), "Diagonally adjacent wire should have 'connected' tag"

    def test_no_roots_no_closure_tag(self):
        """If no objects match root config, no closure tag should be applied."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "W", ".", "#"],
                ["#", ".", "@", ".", "#"],
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "W": "wire"},
        )
        cfg.game.actions.noop.enabled = True

        cfg.game.objects["wire"] = GridObjectConfig(
            name="wire",
            map_name="wire",
            tags=[typeTag("wire")],
        )

        cfg.game.tags = [typeTag("hub")]
        cfg.game.materialize_queries = [
            MaterializedQuery(
                tag="connected",
                query=ClosureQuery(
                    source=typeTag("hub"),
                    bridge=[TagFilter(target=HandlerTarget.TARGET, tag=typeTag("wire"))],
                    radius=1,
                ),
            ),
        ]

        sim = Simulation(cfg)
        has_tag = _make_tag_checker(sim, cfg)

        assert not has_tag("connected", 2, 2), "Wire should NOT have 'connected' tag without any hub"


class TestAdvancedClosure:
    """Test advanced closure tag features."""

    def test_custom_radius(self):
        """radius=2 should expand 2 BFS hops through bridge objects."""
        # Hub at (2,2), wires at (2,3) and (2,4) — a chain of 2 bridge hops
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", ".", ".", "#"],
                ["#", ".", "H", "W", "W", ".", "#"],
                ["#", ".", ".", ".", ".", ".", "#"],
                ["#", ".", ".", "@", ".", ".", "#"],
                ["#", "#", "#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "H": "hub", "W": "wire"},
        )
        cfg.game.actions.noop.enabled = True

        cfg.game.objects["hub"] = GridObjectConfig(
            name="hub",
            map_name="hub",
            tags=[typeTag("hub")],
        )
        cfg.game.objects["wire"] = GridObjectConfig(
            name="wire",
            map_name="wire",
            tags=[typeTag("wire")],
        )

        cfg.game.materialize_queries = [
            MaterializedQuery(
                tag="r1",
                query=ClosureQuery(
                    source=typeTag("hub"),
                    bridge=[TagFilter(target=HandlerTarget.TARGET, tag=typeTag("wire"))],
                    radius=1,
                ),
            ),
            MaterializedQuery(
                tag="r2",
                query=ClosureQuery(
                    source=typeTag("hub"),
                    bridge=[TagFilter(target=HandlerTarget.TARGET, tag=typeTag("wire"))],
                    radius=2,
                ),
            ),
        ]

        sim = Simulation(cfg)
        has_tag = _make_tag_checker(sim, cfg)

        # radius=1: hub expands to immediate neighbor wire only
        assert has_tag("r1", 2, 2), "Hub should have 'r1' tag"
        assert has_tag("r1", 2, 3), "Wire at hop 1 should have 'r1' tag"
        assert not has_tag("r1", 2, 4), "Wire at hop 2 should NOT have 'r1' tag"

        # radius=2: hub expands 2 hops through bridge wires
        assert has_tag("r2", 2, 2), "Hub should have 'r2' tag"
        assert has_tag("r2", 2, 3), "Wire at hop 1 should have 'r2' tag"
        assert has_tag("r2", 2, 4), "Wire at distance 2 should have 'r2' tag (radius=2)"

    def test_multiple_closures(self):
        """Two independent MaterializedQuery entries should work simultaneously."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", ".", ".", "#"],
                ["#", ".", "H", "W", ".", ".", "#"],
                ["#", ".", ".", ".", ".", ".", "#"],
                ["#", ".", ".", "P", "C", ".", "#"],
                ["#", ".", ".", "@", ".", ".", "#"],
                ["#", "#", "#", "#", "#", "#", "#"],
            ],
            char_to_map_name={
                "#": "wall",
                "@": "agent.agent",
                ".": "empty",
                "H": "hub",
                "W": "wire",
                "P": "power",
                "C": "cable",
            },
        )
        cfg.game.actions.noop.enabled = True

        cfg.game.objects["hub"] = GridObjectConfig(
            name="hub",
            map_name="hub",
            tags=[typeTag("hub")],
        )
        cfg.game.objects["wire"] = GridObjectConfig(
            name="wire",
            map_name="wire",
            tags=[typeTag("wire")],
        )
        cfg.game.objects["power"] = GridObjectConfig(
            name="power",
            map_name="power",
            tags=[typeTag("power")],
        )
        cfg.game.objects["cable"] = GridObjectConfig(
            name="cable",
            map_name="cable",
            tags=[typeTag("cable")],
        )

        cfg.game.materialize_queries = [
            MaterializedQuery(
                tag="net1",
                query=ClosureQuery(
                    source=typeTag("hub"),
                    bridge=[TagFilter(target=HandlerTarget.TARGET, tag=typeTag("wire"))],
                    radius=1,
                ),
            ),
            MaterializedQuery(
                tag="net2",
                query=ClosureQuery(
                    source=typeTag("power"),
                    bridge=[TagFilter(target=HandlerTarget.TARGET, tag=typeTag("cable"))],
                    radius=1,
                ),
            ),
        ]

        sim = Simulation(cfg)
        has_tag = _make_tag_checker(sim, cfg)

        assert has_tag("net1", 2, 2), "Hub should have 'net1' tag"
        assert has_tag("net1", 2, 3), "Wire should have 'net1' tag"
        assert not has_tag("net1", 4, 3), "Power should NOT have 'net1' tag"
        assert not has_tag("net1", 4, 4), "Cable should NOT have 'net1' tag"

        assert has_tag("net2", 4, 3), "Power should have 'net2' tag"
        assert has_tag("net2", 4, 4), "Cable should have 'net2' tag"
        assert not has_tag("net2", 2, 2), "Hub should NOT have 'net2' tag"
        assert not has_tag("net2", 2, 3), "Wire should NOT have 'net2' tag"


class TestNestedQueryConstraints:
    """Outer query constraints must be preserved when source is a sub-query."""

    def _make_alpha_beta_config(self):
        """Two object types sharing a 'selectable' tag on a small grid."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", ".", ".", "#"],
                ["#", ".", "A", ".", "B", ".", "#"],
                ["#", ".", ".", ".", ".", ".", "#"],
                ["#", ".", ".", "@", ".", ".", "#"],
                ["#", "#", "#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "A": "alpha", "B": "beta"},
        )
        cfg.game.actions.noop.enabled = True
        cfg.game.tags = ["selectable"]

        cfg.game.objects["alpha"] = GridObjectConfig(
            name="alpha",
            map_name="alpha",
            tags=[typeTag("alpha"), "selectable"],
        )
        cfg.game.objects["beta"] = GridObjectConfig(
            name="beta",
            map_name="beta",
            tags=[typeTag("beta"), "selectable"],
        )
        return cfg

    def test_nested_query_filters_applied(self):
        """query(inner_query, filters=[...]) must apply the outer filters."""
        cfg = self._make_alpha_beta_config()
        inner = Query(source="selectable")
        outer = Query(
            source=inner,
            filters=[TagFilter(target=HandlerTarget.TARGET, tag=typeTag("alpha"))],
        )
        cfg.game.materialize_queries = [
            MaterializedQuery(tag="chosen", query=outer),
        ]

        sim = Simulation(cfg)
        has_tag = _make_tag_checker(sim, cfg)

        assert has_tag("chosen", 2, 2), "Alpha should have 'chosen' tag"
        assert not has_tag("chosen", 2, 4), "Beta should NOT have 'chosen' (outer filter requires type:alpha)"

    def test_nested_query_max_items_applied(self):
        """query(inner_query, max_items=N) must limit results to N."""
        cfg = self._make_alpha_beta_config()
        inner = Query(source="selectable")
        outer = Query(source=inner, max_items=1)
        cfg.game.materialize_queries = [
            MaterializedQuery(tag="chosen", query=outer),
        ]

        sim = Simulation(cfg)
        has_tag = _make_tag_checker(sim, cfg)

        tagged_count = sum(1 for r, c in [(2, 2), (2, 4)] if has_tag("chosen", r, c))
        assert tagged_count == 1, f"max_items=1 should tag exactly 1 object, got {tagged_count}"
