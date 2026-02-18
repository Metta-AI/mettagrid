"""Tests for tag bitset: O(1) has_tag via std::bitset<kMaxTags>.

Verifies that tag mutations (add/remove) correctly update the bitset,
and that lookups, TagIndex counts, and TagFilter all reflect the changes.
"""

from mettagrid.config.filter import TagFilter
from mettagrid.config.filter.filter import HandlerTarget
from mettagrid.config.handler_config import AOEConfig
from mettagrid.config.mettagrid_config import (
    GridObjectConfig,
    MettaGridConfig,
    ResourceLimitsConfig,
)
from mettagrid.config.mutation import (
    EntityTarget,
    ResourceDeltaMutation,
    addTag,
    removeTag,
)
from mettagrid.config.tag import tag
from mettagrid.simulator import Simulation

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sim(ascii_map, objects=None, tags=None, resource_names=None, num_agents=1):
    """Create a simple simulation from an ASCII map."""
    cfg = MettaGridConfig.EmptyRoom(num_agents=num_agents, with_walls=True).with_ascii_map(
        ascii_map,
        char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", **{k: k for k in (objects or {}).keys()}},
    )
    cfg.game.actions.noop.enabled = True
    if tags:
        cfg.game.agent.tags = tags
    if resource_names:
        cfg.game.resource_names = resource_names
    if objects:
        for name, obj_cfg in objects.items():
            cfg.game.objects[name] = obj_cfg
    return cfg, Simulation(cfg)


def _tag_id(cfg, name):
    id_map = cfg.game.id_map()
    tag_names = id_map.tag_names()
    return {n: i for i, n in enumerate(tag_names)}[name]


def _agent_obj(sim):
    for _id, obj in sim._c_sim.grid_objects().items():
        if obj["type_name"] == "agent":
            return obj
    raise RuntimeError("No agent found")


# ===========================================================================
# 1. Direct has_tag / add_tag / remove_tag via Python bindings
# ===========================================================================


class TestDirectTagMethods:
    """Test has_tag/add_tag/remove_tag called directly on grid objects."""

    def test_has_tag_reflects_initial_tags(self):
        cfg, sim = _make_sim(
            [[".", "@", "."], [".", ".", "."], [".", ".", "."]],
            tags=["alpha", "beta"],
        )
        agent = _agent_obj(sim)
        assert agent["has_tag"](_tag_id(cfg, "alpha"))
        assert agent["has_tag"](_tag_id(cfg, "beta"))

    def test_add_tag_makes_has_tag_true(self):
        cfg, sim = _make_sim(
            [[".", "@", "."], [".", ".", "."], [".", ".", "."]],
            tags=["extra"],
        )
        agent = _agent_obj(sim)
        extra_id = _tag_id(cfg, "extra")
        # Agent has "extra" from agent tags; remove then re-add
        agent["remove_tag"](extra_id)
        assert not agent["has_tag"](extra_id)
        agent["add_tag"](extra_id)
        assert agent["has_tag"](extra_id)

    def test_remove_tag_makes_has_tag_false(self):
        cfg, sim = _make_sim(
            [[".", "@", "."], [".", ".", "."], [".", ".", "."]],
            tags=["removable"],
        )
        agent = _agent_obj(sim)
        rid = _tag_id(cfg, "removable")
        assert agent["has_tag"](rid)
        agent["remove_tag"](rid)
        assert not agent["has_tag"](rid)

    def test_add_remove_cycle(self):
        cfg, sim = _make_sim(
            [[".", "@", "."], [".", ".", "."], [".", ".", "."]],
            tags=["cycle"],
        )
        agent = _agent_obj(sim)
        cid = _tag_id(cfg, "cycle")
        assert agent["has_tag"](cid)
        agent["remove_tag"](cid)
        assert not agent["has_tag"](cid)
        agent["add_tag"](cid)
        assert agent["has_tag"](cid)

    def test_add_tag_idempotent(self):
        cfg, sim = _make_sim(
            [[".", "@", "."], [".", ".", "."], [".", ".", "."]],
            tags=["once"],
        )
        agent = _agent_obj(sim)
        oid = _tag_id(cfg, "once")
        agent["add_tag"](oid)
        agent["add_tag"](oid)
        assert agent["has_tag"](oid)

    def test_remove_nonexistent_is_noop(self):
        cfg, sim = _make_sim(
            [[".", "@", "."], [".", ".", "."], [".", ".", "."]],
            tags=["keep"],
        )
        agent = _agent_obj(sim)
        kid = _tag_id(cfg, "keep")
        # Remove a tag the agent doesn't have (use an out-of-range ID)
        agent["remove_tag"](200)
        assert agent["has_tag"](kid)

    def test_has_tag_out_of_range(self):
        _cfg, sim = _make_sim(
            [[".", "@", "."], [".", ".", "."], [".", ".", "."]],
        )
        agent = _agent_obj(sim)
        assert not agent["has_tag"](999)
        assert not agent["has_tag"](-1)


# ===========================================================================
# 2. Tag mutations via AOE -> has_tag + TagIndex
# ===========================================================================


class TestTagMutationUpdatesLookup:
    """Verify that addTag/removeTag mutations correctly update has_tag and TagIndex."""

    def test_aoe_add_tag_updates_has_tag(self):
        cfg, sim = _make_sim(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],
                ["#", ".", "T", ".", "#"],
                ["#", "#", "#", "#", "#"],
            ],
            objects={
                "T": GridObjectConfig(
                    name="tagger",
                    map_name="T",
                    tags=["marked"],
                    aoes={"default": AOEConfig(radius=2, filters=[], mutations=[addTag(tag("marked"))])},
                )
            },
        )
        agent = _agent_obj(sim)
        mid = _tag_id(cfg, "marked")
        assert not agent["has_tag"](mid)

        sim.agent(0).set_action("noop")
        sim.step()

        agent = _agent_obj(sim)
        assert agent["has_tag"](mid)

    def test_aoe_add_tag_updates_tag_index(self):
        cfg, sim = _make_sim(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],
                ["#", ".", "T", ".", "#"],
                ["#", "#", "#", "#", "#"],
            ],
            objects={
                "T": GridObjectConfig(
                    name="tagger",
                    map_name="T",
                    tags=["tracked"],
                    aoes={"default": AOEConfig(radius=2, filters=[], mutations=[addTag(tag("tracked"))])},
                )
            },
        )
        tag_index = sim._c_sim.tag_index()
        tid = _tag_id(cfg, "tracked")

        initial_count = tag_index.count_objects_with_tag(tid)

        sim.agent(0).set_action("noop")
        sim.step()

        assert tag_index.count_objects_with_tag(tid) == initial_count + 1

    def test_aoe_remove_tag_updates_has_tag(self):
        cfg, sim = _make_sim(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],
                ["#", ".", "C", ".", "#"],
                ["#", "#", "#", "#", "#"],
            ],
            tags=["cursed"],
            objects={
                "C": GridObjectConfig(
                    name="cleanser",
                    map_name="C",
                    aoes={"default": AOEConfig(radius=2, filters=[], mutations=[removeTag(tag("cursed"))])},
                )
            },
        )
        agent = _agent_obj(sim)
        cid = _tag_id(cfg, "cursed")
        assert agent["has_tag"](cid)

        sim.agent(0).set_action("noop")
        sim.step()

        agent = _agent_obj(sim)
        assert not agent["has_tag"](cid)

    def test_aoe_remove_tag_updates_tag_index(self):
        cfg, sim = _make_sim(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],
                ["#", ".", "C", ".", "#"],
                ["#", "#", "#", "#", "#"],
            ],
            tags=["doomed"],
            objects={
                "C": GridObjectConfig(
                    name="cleanser",
                    map_name="C",
                    aoes={"default": AOEConfig(radius=2, filters=[], mutations=[removeTag(tag("doomed"))])},
                )
            },
        )
        tag_index = sim._c_sim.tag_index()
        did = _tag_id(cfg, "doomed")
        initial_count = tag_index.count_objects_with_tag(did)
        assert initial_count >= 1

        sim.agent(0).set_action("noop")
        sim.step()

        assert tag_index.count_objects_with_tag(did) == initial_count - 1


# ===========================================================================
# 3. Tag mutations + TagFilter interaction
# ===========================================================================


class TestTagMutationWithFilters:
    """Verify that TagFilter sees tags added/removed by mutations."""

    def test_add_tag_enables_tag_filter(self):
        """After addTag, a TagFilter checking that tag should pass."""
        cfg, sim = _make_sim(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],
                ["#", "T", "G", ".", "#"],
                ["#", "#", "#", "#", "#"],
            ],
            resource_names=["gold"],
            objects={
                "T": GridObjectConfig(
                    name="tagger",
                    map_name="T",
                    tags=["vip"],
                    aoes={"default": AOEConfig(radius=2, filters=[], mutations=[addTag(tag("vip"))])},
                ),
                "G": GridObjectConfig(
                    name="giver",
                    map_name="G",
                    aoes={
                        "default": AOEConfig(
                            radius=2,
                            filters=[TagFilter(target=HandlerTarget.TARGET, tag=tag("vip"))],
                            mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"gold": 50})],
                        )
                    },
                ),
            },
        )
        cfg.game.agent.inventory.initial = {"gold": 0}
        cfg.game.agent.inventory.limits = {"gold": ResourceLimitsConfig(min=1000, resources=["gold"])}
        sim = Simulation(cfg)

        sim.agent(0).set_action("noop")
        sim.step()

        gold = sim.agent(0).inventory.get("gold", 0)
        assert gold == 50, f"Agent with 'vip' tag should get gold, got {gold}"

    def test_remove_tag_disables_tag_filter(self):
        """After removeTag, a TagFilter checking that tag should fail on the next step."""
        cfg, sim = _make_sim(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],
                ["#", ".", "D", ".", "#"],
                ["#", "#", "#", "#", "#"],
            ],
            tags=["vulnerable"],
            resource_names=["hp"],
            objects={
                "D": GridObjectConfig(
                    name="damager",
                    map_name="D",
                    aoes={
                        "default": AOEConfig(
                            radius=2,
                            filters=[TagFilter(target=HandlerTarget.TARGET, tag=tag("vulnerable"))],
                            mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"hp": -30})],
                        )
                    },
                ),
            },
        )
        cfg.game.agent.inventory.initial = {"hp": 100}
        cfg.game.agent.inventory.limits = {"hp": ResourceLimitsConfig(min=1000, resources=["hp"])}
        sim = Simulation(cfg)

        # Step 1: damager should fire (agent has "vulnerable")
        sim.agent(0).set_action("noop")
        sim.step()
        hp_after_step1 = sim.agent(0).inventory.get("hp", 0)
        assert hp_after_step1 < 100, f"Agent with 'vulnerable' should take damage, got hp={hp_after_step1}"

        # Directly remove the tag
        agent = _agent_obj(sim)
        vid = _tag_id(cfg, "vulnerable")
        agent["remove_tag"](vid)

        # Step 2: damager should NOT fire (tag removed)
        sim.agent(0).set_action("noop")
        sim.step()
        hp_after_step2 = sim.agent(0).inventory.get("hp", 0)
        assert hp_after_step2 == hp_after_step1, (
            f"Agent without 'vulnerable' should not take more damage, hp went from {hp_after_step1} to {hp_after_step2}"
        )


# ===========================================================================
# 4. Multi-step mutation sequences
# ===========================================================================


class TestMultiStepTagMutations:
    """Verify tags are correct across multiple simulation steps."""

    def test_add_then_remove_across_steps(self):
        """Tag added in step 1, removed in step 2."""
        cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
            [
                ["#", "#", "#", "#", "#"],
                ["#", ".", ".", ".", "#"],
                ["#", ".", "@", ".", "#"],
                ["#", "A", "R", ".", "#"],
                ["#", "#", "#", "#", "#"],
            ],
            char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "A": "adder", "R": "remover"},
        )
        cfg.game.actions.noop.enabled = True

        # Step 1 event adds "temp" tag
        cfg.game.objects["adder"] = GridObjectConfig(
            name="adder",
            map_name="adder",
            tags=["temp"],
            aoes={"default": AOEConfig(radius=2, filters=[], mutations=[addTag(tag("temp"))])},
        )
        # Step 2 event removes "temp" tag (only fires on agents that have it)
        cfg.game.objects["remover"] = GridObjectConfig(
            name="remover",
            map_name="remover",
            aoes={
                "default": AOEConfig(
                    radius=2,
                    filters=[TagFilter(target=HandlerTarget.TARGET, tag=tag("temp"))],
                    mutations=[removeTag(tag("temp"))],
                )
            },
        )

        sim = Simulation(cfg)
        id_map = cfg.game.id_map()
        tag_names = id_map.tag_names()
        tag_name_to_id = {n: i for i, n in enumerate(tag_names)}
        temp_id = tag_name_to_id["temp"]

        # Initially no tag
        agent = _agent_obj(sim)
        assert not agent["has_tag"](temp_id)

        # Step 1: adder adds "temp", then remover sees it and removes
        sim.agent(0).set_action("noop")
        sim.step()

        # After two steps, remover has had a chance to fire with the tag present
        sim.agent(0).set_action("noop")
        sim.step()

        agent = _agent_obj(sim)
        # After adder adds and remover removes, the agent should no longer have the tag
        assert not agent["has_tag"](temp_id)
