from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast

from mettagrid.renderer.mettascope import (
    MettascopeRenderer,
    _extract_tutorial_overlay_phases,
)


def test_extract_tutorial_overlay_phases_prefers_first_non_empty_list() -> None:
    overlay = _extract_tutorial_overlay_phases(
        {
            0: {"tutorial_overlay_phases": []},
            1: {"tutorial_overlay_phases": ["Step 1", "Step 2"]},
            2: {"tutorial_overlay_phases": ["Later Step"]},
        }
    )

    assert overlay == ["Step 1", "Step 2"]


def test_extract_tutorial_overlay_phases_ignores_non_dict_infos() -> None:
    overlay = _extract_tutorial_overlay_phases({0: "not-a-dict", 1: {"other_key": "value"}})
    assert overlay == []


class _FakeMettascopeModule(ModuleType):
    def __init__(self) -> None:
        super().__init__("mettascope")
        self.calls: list[str] = []

    def render(self, step: int, replay_step: str):  # type: ignore[no-untyped-def]
        _ = replay_step
        self.calls.append(f"render:{step}")
        return SimpleNamespace(should_close=False, actions=[])

    def render_pending(self):  # type: ignore[no-untyped-def]
        self.calls.append("render_pending")
        return SimpleNamespace(should_close=False, actions=[])


class _FakeSimulation:
    def __init__(self) -> None:
        self.current_step = 7
        self.num_agents = 1
        self.episode_rewards = [0.0]
        self.action_success = []
        self.resource_names: list[str] = []
        self._context = {"policy_infos": {}}
        self._c_sim = SimpleNamespace(get_episode_stats=lambda: {})

    def grid_objects(self, ignore_types=None):  # type: ignore[no-untyped-def]
        _ = ignore_types
        return {}

    def end_episode(self) -> None:
        raise AssertionError("render_pending should not close the episode")


def test_mettascope_renderer_uses_pending_binding_without_building_replay(monkeypatch) -> None:
    fake_module = _FakeMettascopeModule()
    monkeypatch.setitem(sys.modules, "mettascope", fake_module)
    monkeypatch.setattr("mettagrid.renderer.mettascope._resolve_nim_root", lambda: Path("/tmp"))

    renderer = MettascopeRenderer()
    renderer.set_simulation(cast(Any, _FakeSimulation()))
    monkeypatch.setattr(
        renderer,
        "_build_step_replay",
        lambda: (_ for _ in ()).throw(AssertionError("render_pending should not rebuild replay state")),
    )

    assert renderer.supports_pending_render() is True

    renderer.render_pending()

    assert fake_module.calls == ["render_pending"]
