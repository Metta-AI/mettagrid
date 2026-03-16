import os

from mettagrid.renderer.miniscope import miniscope as miniscope_module
from mettagrid.renderer.miniscope.miniscope import MiniscopeRenderer
from mettagrid.renderer.renderer import NoRenderer
from mettagrid.types import Action


class _DummyAgent:
    def __init__(self) -> None:
        self.actions: list[Action] = []

    def set_action(self, action: Action) -> None:
        self.actions.append(action)


class _DummySim:
    def __init__(self) -> None:
        self._agents = {0: _DummyAgent(), 1: _DummyAgent()}

    def agent(self, agent_id: int) -> _DummyAgent:
        return self._agents[agent_id]


def test_apply_deferred_user_actions_applies_and_clears_queue() -> None:
    renderer = NoRenderer()
    renderer._sim = _DummySim()
    first_action = Action(name="move_north")
    second_action = Action(name="noop")

    renderer.defer_user_action(0, first_action)
    renderer.defer_user_action(1, second_action)
    renderer.apply_deferred_user_actions()

    assert renderer._sim.agent(0).actions == [first_action]
    assert renderer._sim.agent(1).actions == [second_action]
    assert renderer._deferred_user_actions == []


def test_miniscope_renderer_uses_default_terminal_size_when_invalid(monkeypatch) -> None:
    monkeypatch.setattr(
        miniscope_module.shutil,
        "get_terminal_size",
        lambda fallback=(0, 0): os.terminal_size((0, 0)),
    )

    renderer = MiniscopeRenderer()

    assert renderer._initial_terminal_columns == 120
    assert renderer._initial_terminal_lines == 40
