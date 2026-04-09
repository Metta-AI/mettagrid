"""Tests for the QuerySystem (MaterializedQuery + ClosureQuery).

These tests verify that:
1. Materialized queries are computed correctly via BFS from source through candidates
2. Disconnected components don't receive the materialized tag
3. Diagonal adjacency works (maxDistance(1) as edge filter)
4. No roots means no materialized tag applied
5. Edge filter radius controls hop distance in BFS
6. Multiple independent materialized queries work simultaneously
"""

from mettagrid.config.filter import HandlerTarget, TagFilter, maxDistance
from mettagrid.config.game_value import ConstValue, GameValueRatio, QueryCountValue, val
from mettagrid.config.handler_config import Handler
from mettagrid.config.mettagrid_config import (
    GridObjectConfig,
    InventoryConfig,
    MettaGridConfig,
    ResourceLimitsConfig,
)
from mettagrid.config.mutation.query_inventory_mutation import queryDelta
from mettagrid.config.query import ClosureQuery, MaterializedQuery, Query, query
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
        """Hub (source) + adjacent wires (candidates) should all get the closure tag."""
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
                    candidates=query(typeTag("wire")),
                    edge_filters=[maxDistance(1)],
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
                    candidates=query(typeTag("wire")),
                    edge_filters=[maxDistance(1)],
                ),
            ),
        ]

        sim = Simulation(cfg)
        has_tag = _make_tag_checker(sim, cfg)

        assert has_tag("connected", 2, 3), "Wire next to hub should have 'connected' tag"
        assert not has_tag("connected", 2, 5), "Disconnected wire should NOT have 'connected' tag"

    def test_diagonal_adjacency(self):
        """Wire diagonally adjacent to hub should get tagged (L2 distance sqrt(2))."""
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
                    candidates=query(typeTag("wire")),
                    edge_filters=[maxDistance(2)],
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
                    candidates=query(typeTag("wire")),
                    edge_filters=[maxDistance(1)],
                ),
            ),
        ]

        sim = Simulation(cfg)
        has_tag = _make_tag_checker(sim, cfg)

        assert not has_tag("connected", 2, 2), "Wire should NOT have 'connected' tag without any hub"


class TestAdvancedClosure:
    """Test advanced closure tag features."""

    def test_edge_filter_radius_controls_hop_distance(self):
        """maxDistance radius in edge_filters controls how far BFS expands per hop.

        Map: H . W (hub at (2,2), empty at (2,3), wire at (2,4))
        radius=1: wire is at L2 distance 2 from hub — unreachable in 1 hop
        radius=2: wire is within reach — hub can reach wire directly
        """
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", ".", ".", "#"],
                ["#", ".", "H", ".", "W", ".", "#"],
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
                    candidates=query(typeTag("wire")),
                    edge_filters=[maxDistance(1)],
                ),
            ),
            MaterializedQuery(
                tag="r2",
                query=ClosureQuery(
                    source=typeTag("hub"),
                    candidates=query(typeTag("wire")),
                    edge_filters=[maxDistance(2)],
                ),
            ),
        ]

        sim = Simulation(cfg)
        has_tag = _make_tag_checker(sim, cfg)

        # radius=1: wire is 2 cells away, beyond the 1-cell hop distance
        assert has_tag("r1", 2, 2), "Hub should have 'r1' tag"
        assert not has_tag("r1", 2, 4), "Wire at distance 2 should NOT have 'r1' tag (radius=1)"

        # radius=2: wire is within the 2-cell hop distance
        assert has_tag("r2", 2, 2), "Hub should have 'r2' tag"
        assert has_tag("r2", 2, 4), "Wire at distance 2 should have 'r2' tag (radius=2)"

    def test_closure_query_max_items_uses_deterministic_closure_order(self):
        """ClosureQuery max_items should preserve deterministic closure discovery order."""
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
                tag="connected_one",
                query=ClosureQuery(
                    source=typeTag("hub"),
                    candidates=query(typeTag("wire")),
                    edge_filters=[maxDistance(1)],
                    max_items=1,
                ),
            ),
        ]

        sim = Simulation(cfg, seed=42)
        has_tag = _make_tag_checker(sim, cfg)

        assert has_tag("connected_one", 2, 3), "Closure roots should stay first when max_items truncates results"
        assert not has_tag("connected_one", 2, 2), "Reachable wires should be dropped once max_items selects the hub"
        assert not has_tag("connected_one", 2, 4), "Reachable wires should be dropped once max_items selects the hub"
        assert not has_tag("connected_one", 3, 3), "Reachable wires should be dropped once max_items selects the hub"

    def test_adjacent_chain_with_radius_1(self):
        """Adjacent candidates chain indefinitely with maxDistance(1).

        Map: H W W — hub expands to wire1, then wire1 expands to wire2.
        """
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
                tag="net",
                query=ClosureQuery(
                    source=typeTag("hub"),
                    candidates=query(typeTag("wire")),
                    edge_filters=[maxDistance(1)],
                ),
            ),
        ]

        sim = Simulation(cfg)
        has_tag = _make_tag_checker(sim, cfg)

        assert has_tag("net", 2, 2), "Hub should have 'net' tag"
        assert has_tag("net", 2, 3), "Adjacent wire should have 'net' tag"
        assert has_tag("net", 2, 4), "Chained wire should have 'net' tag (adjacent to first wire)"

    def test_max_distance_zero_is_unlimited(self):
        """maxDistance(0) means unlimited range — all candidates are reachable.

        Map: H . . . W  (hub at (2,2), wire at (2,6) — distance 4)
        radius=1: wire is far beyond 1 hop — NOT reachable
        radius=0: unlimited — wire IS reachable regardless of distance
        """
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", ".", ".", ".", ".", "#"],
                ["#", ".", "H", ".", ".", ".", "W", ".", "#"],
                ["#", ".", ".", ".", ".", ".", ".", ".", "#"],
                ["#", ".", ".", ".", "@", ".", ".", ".", "#"],
                ["#", "#", "#", "#", "#", "#", "#", "#", "#"],
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
                tag="limited",
                query=ClosureQuery(
                    source=typeTag("hub"),
                    candidates=query(typeTag("wire")),
                    edge_filters=[maxDistance(1)],
                ),
            ),
            MaterializedQuery(
                tag="unlimited",
                query=ClosureQuery(
                    source=typeTag("hub"),
                    candidates=query(typeTag("wire")),
                    edge_filters=[maxDistance(0)],
                ),
            ),
        ]

        sim = Simulation(cfg)
        has_tag = _make_tag_checker(sim, cfg)

        assert not has_tag("limited", 2, 6), "Wire at distance 4 should NOT have 'limited' tag (radius=1)"
        assert has_tag("unlimited", 2, 2), "Hub should have 'unlimited' tag"
        assert has_tag("unlimited", 2, 6), "Wire at distance 4 should have 'unlimited' tag (radius=0 = unlimited)"

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
                    candidates=query(typeTag("wire")),
                    edge_filters=[maxDistance(1)],
                ),
            ),
            MaterializedQuery(
                tag="net2",
                query=ClosureQuery(
                    source=typeTag("power"),
                    candidates=query(typeTag("cable")),
                    edge_filters=[maxDistance(1)],
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


class TestGameValueMaxItems:
    """Query.max_items accepts GameValue for runtime-computed limits."""

    def _make_chest_grid(self, num_chests: int, max_items_gv):
        """Create a grid with N chests and an on_tick handler that adds gold using a GameValue max_items query."""
        rows = [["@"] + ["C"] * num_chests + ["."] * (5 - num_chests)]
        for _ in range(4):
            rows.append(["."] * (num_chests + 1 + (5 - num_chests)))
        width = num_chests + 1 + (5 - num_chests)

        cfg = MettaGridConfig.EmptyRoom(num_agents=1, width=width, height=5, border_width=0).with_ascii_map(
            rows,
            char_to_map_name={"@": "agent.agent", ".": "empty", "C": "chest"},
        )
        cfg.game.resource_names = ["gold"]
        cfg.game.agent.inventory.initial = {"gold": 0}
        cfg.game.agent.inventory.limits = {
            "gold": ResourceLimitsConfig(base=1000, resources=["gold"]),
        }
        cfg.game.objects["chest"] = GridObjectConfig(
            name="chest",
            map_name="chest",
            inventory=InventoryConfig(initial={"gold": 0}, default_limit=1000),
        )
        cfg.game.actions.noop.enabled = True

        q = query(typeTag("chest"))
        q.max_items = max_items_gv
        q.order_by = "random"
        cfg.game.on_tick["refill"] = Handler(
            mutations=[queryDelta(q, {"gold": 100})],
        )
        return cfg

    def _chest_golds(self, sim):
        """Return list of gold amounts for all chests."""
        gold_idx = sim.resource_names.index("gold")
        return [
            obj.get("inventory", {}).get(gold_idx, 0)
            for obj in sim.grid_objects().values()
            if obj.get("type_name") == "chest"
        ]

    def test_const_gamevalue_max_items(self):
        """ConstValue max_items limits mutation to N objects."""
        cfg = self._make_chest_grid(num_chests=4, max_items_gv=ConstValue(value=2.0))
        sim = Simulation(cfg, seed=42)

        sim.agent(0).set_action("noop")
        sim.step()

        golds = self._chest_golds(sim)
        assert len(golds) == 4
        refilled = sum(1 for g in golds if g > 0)
        assert refilled == 2, f"ConstValue(2) should refill exactly 2 chests, got {refilled}"
        sim.close()

    def test_query_count_gamevalue_max_items(self):
        """QueryCountValue max_items = count(all chests) refills all chests."""
        count_gv = QueryCountValue(query=query(typeTag("chest")))
        cfg = self._make_chest_grid(num_chests=3, max_items_gv=count_gv)
        sim = Simulation(cfg, seed=42)

        sim.agent(0).set_action("noop")
        sim.step()

        golds = self._chest_golds(sim)
        refilled = sum(1 for g in golds if g > 0)
        assert refilled == 3, f"QueryCountValue (count=3) should refill all 3 chests, got {refilled}"
        sim.close()

    def test_ratio_gamevalue_max_items(self):
        """GameValueRatio(count, 2) refills half the chests."""
        count_gv = QueryCountValue(query=query(typeTag("chest")))
        ratio_gv = GameValueRatio(count_gv, val(2))
        cfg = self._make_chest_grid(num_chests=4, max_items_gv=ratio_gv)
        sim = Simulation(cfg, seed=42)

        sim.agent(0).set_action("noop")
        sim.step()

        golds = self._chest_golds(sim)
        refilled = sum(1 for g in golds if g > 0)
        assert refilled == 2, f"Ratio(count=4, denom=2) should refill 2 chests, got {refilled}"
        sim.close()

    def test_ratio_gamevalue_accumulates_over_ticks(self):
        """Repeated ticks with random selection eventually refill all chests."""
        count_gv = QueryCountValue(query=query(typeTag("chest")))
        ratio_gv = GameValueRatio(count_gv, val(4))
        cfg = self._make_chest_grid(num_chests=4, max_items_gv=ratio_gv)
        sim = Simulation(cfg, seed=42)

        # 1 out of 4 chests per tick; after enough ticks all should have gold
        for _ in range(50):
            sim.agent(0).set_action("noop")
            sim.step()

        golds = self._chest_golds(sim)
        refilled = sum(1 for g in golds if g > 0)
        assert refilled == 4, f"After 50 ticks, all 4 chests should have gold, got {refilled}"
        sim.close()

    def test_int_max_items_still_works(self):
        """Plain int max_items continues to work (backwards compat)."""
        cfg = self._make_chest_grid(num_chests=4, max_items_gv=1)
        # Override: use plain int instead of GameValue
        q = query(typeTag("chest"))
        q.max_items = 1
        q.order_by = "random"
        cfg.game.on_tick["refill"] = Handler(
            mutations=[queryDelta(q, {"gold": 100})],
        )
        sim = Simulation(cfg, seed=42)

        sim.agent(0).set_action("noop")
        sim.step()

        golds = self._chest_golds(sim)
        refilled = sum(1 for g in golds if g > 0)
        assert refilled == 1, f"int max_items=1 should refill exactly 1 chest, got {refilled}"
        sim.close()
