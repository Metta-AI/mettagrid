import os

from mettagrid.renderer.miniscope import miniscope as miniscope_module
from mettagrid.renderer.miniscope.miniscope import MiniscopeRenderer
from mettagrid.renderer.renderer import NoRenderer
from mettagrid.types import Action


class _DummyAgent:
    def __init__(self) -> None:
        self.actions: list[Action] = []
        self.talk: list[str] = []

    def set_action(self, action: Action) -> None:
        self.actions.append(action)

    def set_talk(self, text: str) -> None:
        self.talk.append(text)


class _DummySim:
    def __init__(self) -> None:
        self._agents = {0: _DummyAgent(), 1: _DummyAgent()}

    def agent(self, agent_id: int) -> _DummyAgent:
        return self._agents[agent_id]


def test_defer_user_action_applies_after_policy_step() -> None:
    renderer = NoRenderer()
    renderer._sim = _DummySim()
    action = Action(name="move_north")

    # defer_user_action queues the action (not applied yet)
    renderer.defer_user_action(0, action)
    assert renderer._sim.agent(0).actions == []
    assert 0 in renderer._pending_user_actions

    # apply_deferred_user_actions applies the action (overriding policy)
    renderer.apply_deferred_user_actions()
    assert renderer._sim.agent(0).actions == [action]

    # Subsequent calls send noops until block expires
    renderer.apply_deferred_user_actions()
    assert renderer._sim.agent(0).actions[-1] == Action(name="noop")

    for _ in range(renderer._BLOCK_POLICY_TICKS - 2):
        renderer.apply_deferred_user_actions()
    assert 0 not in renderer._pending_user_actions


def test_apply_deferred_user_actions_routes_directive_talk() -> None:
    renderer = NoRenderer()
    renderer._sim = _DummySim()

    renderer.defer_user_action(0, Action(name="move_north", talk="hold east"))
    renderer.apply_deferred_user_actions()

    assert renderer._sim.agent(0).actions == [Action(name="move_north")]
    assert renderer._sim.agent(0).talk == ["hold east"]


def test_miniscope_renderer_uses_default_terminal_size_when_invalid(monkeypatch) -> None:
    monkeypatch.setattr(
        miniscope_module.shutil,
        "get_terminal_size",
        lambda fallback=(0, 0): os.terminal_size((0, 0)),
    )

    renderer = MiniscopeRenderer()

    assert renderer._initial_terminal_columns == 120
    assert renderer._initial_terminal_lines == 40
