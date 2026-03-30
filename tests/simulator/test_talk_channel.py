from __future__ import annotations

import pytest

from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    AgentConfig,
    GameConfig,
    MettaGridConfig,
    MoveActionConfig,
    NoopActionConfig,
    ObsConfig,
    TalkConfig,
    WallConfig,
)
from mettagrid.simulator import Action, Location, Simulation
from mettagrid.simulator.talk import ActiveTalk
from mettagrid.test_support.map_builders import ObjectNameMapBuilder


def _make_sim(*, cooldown_steps: int = 3) -> Simulation:
    cfg = MettaGridConfig(
        game=GameConfig(
            max_steps=20,
            num_agents=3,
            obs=ObsConfig(width=5, height=5, num_tokens=64),
            actions=ActionsConfig(noop=NoopActionConfig(), move=MoveActionConfig()),
            talk=TalkConfig(enabled=True, max_length=140, cooldown_steps=cooldown_steps),
            agents=[AgentConfig() for _ in range(3)],
            objects={"wall": WallConfig()},
            map_builder=ObjectNameMapBuilder.Config(
                map_data=[
                    ["wall", "wall", "wall", "wall", "wall", "wall", "wall"],
                    ["wall", "agent.default", "empty", "agent.default", "empty", "empty", "wall"],
                    ["wall", "empty", "empty", "empty", "empty", "empty", "wall"],
                    ["wall", "empty", "empty", "empty", "empty", "empty", "wall"],
                    ["wall", "empty", "empty", "empty", "empty", "agent.default", "wall"],
                    ["wall", "wall", "wall", "wall", "wall", "wall", "wall"],
                ]
            ),
        )
    )
    return Simulation(cfg, seed=7)


def _set_noops(sim: Simulation, *, skip_agent_id: int | None = None) -> None:
    for agent_id in range(sim.num_agents):
        if agent_id == skip_agent_id:
            continue
        sim.agent(agent_id).set_action(Action(name="noop"))


def _talk_texts(sim: Simulation, agent_id: int) -> list[tuple[int, str]]:
    return [(talk.agent_id, talk.text) for talk in sim.agent(agent_id).observation.talk]


def _agent_location(sim: Simulation, agent_id: int) -> tuple[int, int]:
    for grid_object in sim.grid_objects().values():
        if grid_object.get("agent_id") == agent_id:
            location = grid_object["location"]
            return int(location[1]), int(location[0])
    raise AssertionError(f"missing agent_id {agent_id}")


def test_move_and_talk_shares_the_step_and_is_visible_to_nearby_agents() -> None:
    sim = _make_sim()

    sim.agent(0).set_action(Action(name="move_east"))
    sim.agent(0).set_talk("ore on east flank")
    _set_noops(sim, skip_agent_id=0)
    sim.step()

    assert _agent_location(sim, 0) == (1, 2)
    assert _talk_texts(sim, 0) == [(0, "ore on east flank")]
    assert _talk_texts(sim, 1) == [(0, "ore on east flank")]
    assert _talk_texts(sim, 2) == []
    assert sim.agent(1).observation.talk[0].location == (2, 1)


def test_talk_persists_until_cooldown_expires() -> None:
    sim = _make_sim(cooldown_steps=3)

    sim.agent(0).set_action(Action(name="noop"))
    sim.agent(0).set_talk("holding junction")
    _set_noops(sim, skip_agent_id=0)
    sim.step()
    assert _talk_texts(sim, 1) == [(0, "holding junction")]

    for _ in range(2):
        _set_noops(sim)
        sim.step()
        assert _talk_texts(sim, 1) == [(0, "holding junction")]

    _set_noops(sim)
    sim.step()
    assert _talk_texts(sim, 1) == []


def test_talk_states_come_from_simulation_not_context() -> None:
    sim = _make_sim(cooldown_steps=3)

    assert "talk_states" not in sim._context

    sim.agent(0).set_action(Action(name="noop"))
    sim.agent(0).set_talk("holding junction")
    _set_noops(sim, skip_agent_id=0)
    sim.step()

    talk_states = sim.talk_states()
    assert "talk_states" not in sim._context
    assert talk_states[0].text == "holding junction"
    assert talk_states[0].remaining_steps > 0


def test_talk_cooldown_rejects_replacement_before_expiry() -> None:
    sim = _make_sim(cooldown_steps=3)

    sim.agent(0).set_action(Action(name="noop"))
    sim.agent(0).set_talk("first")
    _set_noops(sim, skip_agent_id=0)
    sim.step()

    with pytest.raises(ValueError, match="cooldown"):
        sim.agent(0).set_talk("too soon")


def test_talk_replacement_is_allowed_on_first_legal_resend_step() -> None:
    sim = _make_sim(cooldown_steps=3)

    sim.agent(0).set_action(Action(name="noop"))
    sim.agent(0).set_talk("first")
    _set_noops(sim, skip_agent_id=0)
    sim.step()

    _set_noops(sim)
    sim.step()
    _set_noops(sim)
    sim.step()

    sim.agent(0).set_action(Action(name="noop"))
    sim.agent(0).set_talk("second")
    _set_noops(sim, skip_agent_id=0)
    sim.step()

    assert _talk_texts(sim, 1) == [(0, "second")]


def test_talk_length_limit_is_enforced() -> None:
    sim = _make_sim()

    with pytest.raises(ValueError, match="140"):
        sim.agent(0).set_talk("x" * 141)


def test_visible_talk_returns_empty_when_observer_has_no_location() -> None:
    sim = _make_sim()
    sim._talk_channel._active_by_agent[0] = ActiveTalk(
        text="holding junction",
        expires_after_step=5,
        replace_after_step=3,
    )
    sim._agent_locations_by_id = {0: Location(row=1, col=1)}
    sim._agent_locations_step = sim.current_step

    assert sim._visible_talk(1) == []


def test_zero_cooldown_allows_talk_replacement_on_the_next_step() -> None:
    sim = _make_sim(cooldown_steps=0)

    sim.agent(0).set_action(Action(name="noop"))
    sim.agent(0).set_talk("first")
    _set_noops(sim, skip_agent_id=0)
    sim.step()
    assert _talk_texts(sim, 1) == [(0, "first")]

    sim.agent(0).set_action(Action(name="noop"))
    sim.agent(0).set_talk("second")
    _set_noops(sim, skip_agent_id=0)
    sim.step()

    assert _talk_texts(sim, 1) == [(0, "second")]
