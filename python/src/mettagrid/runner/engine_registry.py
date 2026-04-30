"""Game engine runner registry.

Maps game_engine names to runner callables. Engines register themselves
at import time; dispatch code looks up the registry at runtime.
"""

from __future__ import annotations

from collections.abc import Callable

from mettagrid.runner.types import PureSingleEpisodeJob, PureSingleEpisodeResult

EngineRunner = Callable[[PureSingleEpisodeJob], PureSingleEpisodeResult]
_ENGINE_RUNNERS: dict[str, EngineRunner] = {}


def register_engine_runner(engine: str, runner: EngineRunner) -> None:
    _ENGINE_RUNNERS[engine] = runner


def get_engine_runner(engine: str) -> EngineRunner | None:
    return _ENGINE_RUNNERS.get(engine)


def _lazy_bitworld_runner(job: PureSingleEpisodeJob) -> PureSingleEpisodeResult:
    from mettagrid.runner.bitworld_runner import run_bitworld_episode  # noqa: PLC0415

    return run_bitworld_episode(job)


register_engine_runner("bitworld", _lazy_bitworld_runner)
