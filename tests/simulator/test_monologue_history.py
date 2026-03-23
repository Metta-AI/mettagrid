from mettagrid.config.mettagrid_config import (
    ActionsConfig,
    GameConfig,
    MettaGridConfig,
    MoveActionConfig,
    NoopActionConfig,
    ObsConfig,
    WallConfig,
)
from mettagrid.map_builder.random_map import RandomMapBuilder
from mettagrid.policy.policy import AgentPolicy
from mettagrid.simulator.interface import AgentObservation
from mettagrid.simulator.monologue_projection import compute_monologue_transcript_update
from mettagrid.simulator.rollout import Rollout
from mettagrid.types import Action


class MonologueTailPolicy(AgentPolicy):
    def __init__(self, transcript_tails: list[str]):
        self._transcript_tails = transcript_tails
        self._infos: dict = {}
        self._step = 0

    def step(self, obs: AgentObservation) -> Action:
        _ = obs
        self._infos = {"__monologue_transcript_tail": self._transcript_tails[self._step]}
        self._step += 1
        return Action(name="noop")


def _make_config(num_agents: int = 1, max_steps: int = 2) -> MettaGridConfig:
    return MettaGridConfig(
        game=GameConfig(
            num_agents=num_agents,
            obs=ObsConfig(width=3, height=3, num_tokens=50),
            max_steps=max_steps,
            actions=ActionsConfig(noop=NoopActionConfig(), move=MoveActionConfig()),
            objects={"wall": WallConfig()},
            map_builder=RandomMapBuilder.Config(width=7, height=5, agents=num_agents, seed=42),
        )
    )


def test_compute_monologue_transcript_update_handles_append_overlap_and_reset():
    assert compute_monologue_transcript_update("", "assistant: hello") == ("assistant: hello", False)
    assert compute_monologue_transcript_update("assistant: hello", "assistant: hello\nuser: hi") == (
        "\nuser: hi",
        False,
    )
    assert compute_monologue_transcript_update("abc123", "c123XYZ") == ("XYZ", False)
    assert compute_monologue_transcript_update("old tail", "completely new") == ("completely new", True)


def test_compute_monologue_transcript_update_handles_large_repeated_overlap():
    repeated = "a" * 4096
    assert compute_monologue_transcript_update("b" + repeated, repeated + "c") == ("c", False)


def test_monologue_transcript_tail_is_extracted_into_monologue_updates():
    rollout = Rollout(
        _make_config(max_steps=1),
        [MonologueTailPolicy(["assistant: hello"])],
        policy_names=["debug_policy"],
        max_action_time_ms=10_000,
    )

    rollout.step()

    assert rollout._policy_infos[0] == {"policy_name": "debug_policy"}
    assert rollout._sim._context["monologue_updates"] == {
        0: {"monologue_append": "assistant: hello", "monologue_reset": False}
    }


def test_rollout_emits_only_monologue_append_delta_per_step():
    rollout = Rollout(
        _make_config(),
        [MonologueTailPolicy(["assistant: hello", "assistant: hello\nuser: hi"])],
        policy_names=["debug_policy"],
        max_action_time_ms=10_000,
    )

    rollout.step()
    assert rollout._sim._context["monologue_updates"] == {
        0: {"monologue_append": "assistant: hello", "monologue_reset": False}
    }

    rollout.step()
    assert rollout._sim._context["monologue_updates"] == {
        0: {"monologue_append": "\nuser: hi", "monologue_reset": False}
    }
