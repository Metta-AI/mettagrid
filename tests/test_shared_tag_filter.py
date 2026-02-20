"""Tests for SharedTagPrefixFilter (shared tag prefix matching between actor and target)."""

from mettagrid.config.filter import (
    SharedTagPrefixFilter,
    anyOf,
    isNot,
    sharedTagPrefix,
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


class TestSharedTagPrefixFilter:
    def test_passes_when_actor_and_target_share_tag(self):
        cfg = _base_cfg()
        cfg.game.tags = ["team:red", "team:blue"]
        cfg.game.agent.tags = ["team:red"]
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source", map_name="aoe_source", tags=["team:red"], aoes=_aoe([sharedTagPrefix("team:")])
        )
        assert _run_one_step(cfg) == 10

    def test_fails_when_different_tags(self):
        cfg = _base_cfg()
        cfg.game.tags = ["team:red", "team:blue"]
        cfg.game.agent.tags = ["team:red"]
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source", map_name="aoe_source", tags=["team:blue"], aoes=_aoe([sharedTagPrefix("team:")])
        )
        assert _run_one_step(cfg) == 0

    def test_fails_when_target_has_no_prefix_tag(self):
        cfg = _base_cfg()
        cfg.game.tags = ["team:red", "team:blue"]
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source", map_name="aoe_source", tags=["team:red"], aoes=_aoe([sharedTagPrefix("team:")])
        )
        assert _run_one_step(cfg) == 0

    def test_fails_when_source_has_no_prefix_tag(self):
        cfg = _base_cfg()
        cfg.game.tags = ["team:red", "team:blue"]
        cfg.game.agent.tags = ["team:red"]
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source", map_name="aoe_source", aoes=_aoe([sharedTagPrefix("team:")])
        )
        assert _run_one_step(cfg) == 0


class TestSharedTagPrefixFilterWithNot:
    def test_not_share_tag_passes_for_different_teams(self):
        cfg = _base_cfg()
        cfg.game.tags = ["team:red", "team:blue"]
        cfg.game.agent.tags = ["team:red"]
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            tags=["team:blue"],
            aoes=_aoe([isNot(sharedTagPrefix("team:"))]),
        )
        assert _run_one_step(cfg) == 10

    def test_not_share_tag_fails_for_same_team(self):
        cfg = _base_cfg()
        cfg.game.tags = ["team:red", "team:blue"]
        cfg.game.agent.tags = ["team:red"]
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            tags=["team:red"],
            aoes=_aoe([isNot(sharedTagPrefix("team:"))]),
        )
        assert _run_one_step(cfg) == 0


class TestSharedTagPrefixFilterWithOr:
    def test_or_share_tag_passes_via_first_branch(self):
        cfg = _base_cfg()
        cfg.game.tags = ["team:red", "team:blue", "role:warrior", "role:mage"]
        cfg.game.agent.tags = ["team:red"]
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            tags=["team:red"],
            aoes=_aoe(
                [
                    anyOf(
                        [
                            SharedTagPrefixFilter(tag_prefix="team"),
                            SharedTagPrefixFilter(tag_prefix="role"),
                        ]
                    )
                ]
            ),
        )
        assert _run_one_step(cfg) == 10

    def test_or_share_tag_fails_when_no_branch_matches(self):
        cfg = _base_cfg()
        cfg.game.tags = ["team:red", "team:blue", "role:warrior", "role:mage"]
        cfg.game.agent.tags = ["team:red"]
        cfg.game.objects["aoe_source"] = GridObjectConfig(
            name="aoe_source",
            map_name="aoe_source",
            tags=["team:blue"],
            aoes=_aoe(
                [
                    anyOf(
                        [
                            SharedTagPrefixFilter(tag_prefix="team"),
                            SharedTagPrefixFilter(tag_prefix="role"),
                        ]
                    )
                ]
            ),
        )
        assert _run_one_step(cfg) == 0
