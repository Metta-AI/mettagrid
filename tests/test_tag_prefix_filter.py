"""Tests for TagPrefixFilter (single-entity tag prefix matching)."""

from mettagrid.config.filter import (
    HandlerTarget,
    TagPrefixFilter,
    actorHasTagPrefix,
    anyOf,
    hasTagPrefix,
    isNot,
)
from mettagrid.config.handler_config import AOEConfig
from mettagrid.config.mettagrid_config import GridObjectConfig, MettaGridConfig, ResourceLimitsConfig
from mettagrid.config.mutation import EntityTarget, ResourceDeltaMutation
from mettagrid.simulator import Simulation


def _base_cfg():
    cfg = MettaGridConfig.EmptyRoom(num_agents=1, with_walls=True).with_ascii_map(
        [
            ["#", "#", "#", "#", "#"],
            ["#", ".", ".", ".", "#"],
            ["#", ".", "@", ".", "#"],
            ["#", ".", "S", ".", "#"],
            ["#", "#", "#", "#", "#"],
        ],
        char_to_map_name={"#": "wall", "@": "agent.agent", ".": "empty", "S": "aoe_source"},
    )
    cfg.game.resource_names = ["energy"]
    cfg.game.agent.inventory.initial = {"energy": 0}
    cfg.game.agent.inventory.limits = {"energy": ResourceLimitsConfig(min=1000, resources=["energy"])}
    cfg.game.actions.noop.enabled = True
    return cfg


def _run_one_step(cfg):
    sim = Simulation(cfg)
    sim.agent(0).set_action("noop")
    sim.step()
    return sim.agent(0).inventory.get("energy", 0)


def _aoe(filters):
    return {
        "default": AOEConfig(
            radius=2,
            filters=filters,
            mutations=[ResourceDeltaMutation(target=EntityTarget.TARGET, deltas={"energy": 10})],
        )
    }


class TestTagPrefixFilter:
    def test_passes_when_target_has_matching_prefix_tag(self):
        cfg = _base_cfg()
        cfg.game.tags = ["team:red", "team:blue"]
        cfg.game.agent.tags = ["team:red"]
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source", map_name="aoe_source", aoes=_aoe([hasTagPrefix("team")])
        )
        assert _run_one_step(cfg) == 10

    def test_fails_when_target_has_no_prefix_tag(self):
        cfg = _base_cfg()
        cfg.game.tags = ["team:red", "team:blue"]
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source", map_name="aoe_source", aoes=_aoe([hasTagPrefix("team")])
        )
        assert _run_one_step(cfg) == 0

    def test_passes_with_any_tag_in_prefix_group(self):
        """Agent has team:blue — filter matches any tag with prefix 'team'."""
        cfg = _base_cfg()
        cfg.game.tags = ["team:red", "team:blue"]
        cfg.game.agent.tags = ["team:blue"]
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source", map_name="aoe_source", aoes=_aoe([hasTagPrefix("team")])
        )
        assert _run_one_step(cfg) == 10

    def test_checks_actor_when_target_is_actor(self):
        """TagPrefixFilter with target=ACTOR checks the actor (aoe source), not the target."""
        cfg = _base_cfg()
        cfg.game.tags = ["team:red", "team:blue"]
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            tags=["team:red"],
            aoes=_aoe([TagPrefixFilter(target=HandlerTarget.ACTOR, tag_prefix="team")]),
        )
        assert _run_one_step(cfg) == 10

    def test_actor_check_fails_when_actor_has_no_prefix_tag(self):
        cfg = _base_cfg()
        cfg.game.tags = ["team:red", "team:blue"]
        cfg.game.agent.tags = ["team:red"]
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes=_aoe([TagPrefixFilter(target=HandlerTarget.ACTOR, tag_prefix="team")]),
        )
        assert _run_one_step(cfg) == 0


class TestTagPrefixFilterWithNot:
    def test_not_prefix_passes_when_no_matching_tag(self):
        cfg = _base_cfg()
        cfg.game.tags = ["team:red", "team:blue"]
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source", map_name="aoe_source", aoes=_aoe([isNot(hasTagPrefix("team"))])
        )
        assert _run_one_step(cfg) == 10

    def test_not_prefix_fails_when_has_matching_tag(self):
        cfg = _base_cfg()
        cfg.game.tags = ["team:red", "team:blue"]
        cfg.game.agent.tags = ["team:red"]
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source", map_name="aoe_source", aoes=_aoe([isNot(hasTagPrefix("team"))])
        )
        assert _run_one_step(cfg) == 0


class TestTagPrefixFilterWithOr:
    def test_or_prefix_passes_via_first_branch(self):
        cfg = _base_cfg()
        cfg.game.tags = ["team:red", "team:blue", "role:warrior", "role:mage"]
        cfg.game.agent.tags = ["team:red"]
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes=_aoe([anyOf([hasTagPrefix("team"), hasTagPrefix("role")])]),
        )
        assert _run_one_step(cfg) == 10

    def test_or_prefix_fails_when_no_branch_matches(self):
        cfg = _base_cfg()
        cfg.game.tags = ["team:red", "team:blue", "role:warrior", "role:mage"]
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes=_aoe([anyOf([hasTagPrefix("team"), hasTagPrefix("role")])]),
        )
        assert _run_one_step(cfg) == 0


class TestHasTagPrefixHelper:
    def test_creates_tag_prefix_filter(self):
        f = hasTagPrefix("team")
        assert isinstance(f, TagPrefixFilter)
        assert f.tag_prefix == "team"
        assert f.target == HandlerTarget.TARGET

    def test_creates_with_custom_target(self):
        f = hasTagPrefix("team", target=HandlerTarget.ACTOR)
        assert isinstance(f, TagPrefixFilter)
        assert f.target == HandlerTarget.ACTOR


class TestActorHasTagPrefixHelper:
    def test_creates_actor_targeted_filter(self):
        f = actorHasTagPrefix("team")
        assert isinstance(f, TagPrefixFilter)
        assert f.tag_prefix == "team"
        assert f.target == HandlerTarget.ACTOR

    def test_passes_when_actor_has_matching_prefix(self):
        cfg = _base_cfg()
        cfg.game.tags = ["team:red", "team:blue"]
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            tags=["team:red"],
            aoes=_aoe([actorHasTagPrefix("team")]),
        )
        assert _run_one_step(cfg) == 10

    def test_fails_when_actor_has_no_matching_prefix(self):
        cfg = _base_cfg()
        cfg.game.tags = ["team:red", "team:blue"]
        cfg.game.agent.tags = ["team:red"]
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes=_aoe([actorHasTagPrefix("team")]),
        )
        assert _run_one_step(cfg) == 0

    def test_ignores_target_tags(self):
        """actorHasTagPrefix only checks the actor, not the target — target having the tag doesn't help."""
        cfg = _base_cfg()
        cfg.game.tags = ["team:red", "team:blue"]
        cfg.game.agent.tags = ["team:red"]
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            aoes=_aoe([actorHasTagPrefix("team")]),
        )
        assert _run_one_step(cfg) == 0
