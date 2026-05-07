import copy

import pytest

from mettagrid.runner.types import EpisodeSpec, PureSingleEpisodeJob, SingleEpisodeJob

type RunnerJobModel = type[EpisodeSpec] | type[SingleEpisodeJob] | type[PureSingleEpisodeJob]


@pytest.mark.parametrize(
    "model_cls,extra_fields",
    [
        (EpisodeSpec, {}),
        (SingleEpisodeJob, {}),
        (PureSingleEpisodeJob, {"results_uri": None, "replay_uri": None}),
    ],
)
def test_top_level_game_engine_migration_does_not_mutate_input(
    model_cls: RunnerJobModel, extra_fields: dict[str, object]
) -> None:
    payload = {
        "policy_uris": ["metta://policy/test"],
        "assignments": [0],
        "game_engine": "mettagrid",
        "env": {"game": {"num_agents": 1}},
        **extra_fields,
    }
    original = copy.deepcopy(payload)

    job = model_cls.model_validate(payload)

    assert job.env.game_engine == "mettagrid"
    assert payload == original
