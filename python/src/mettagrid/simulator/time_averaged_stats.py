"""Event handler that accumulates per-step game stats for time-averaging.

Episode-end stats (from ``episode_stats``) only capture the final simulation
state.  For metrics like ``aligned.junction.held`` that fluctuate during an
episode, the end-of-episode snapshot can be misleading.  This handler samples
``episode_stats["game"]`` every step and computes the time-average so callers
can see the full-episode picture.
"""

from __future__ import annotations

from collections import defaultdict

from mettagrid.simulator.interface import SimulatorEventHandler


class TimeAveragedStatsHandler(SimulatorEventHandler):
    """Accumulates game stats at every simulation step."""

    def __init__(self) -> None:
        super().__init__()
        self._step_count: int = 0
        self._accumulated: defaultdict[str, float] = defaultdict(float)

    def on_episode_start(self) -> None:
        super().on_episode_start()
        self._step_count = 0
        self._accumulated.clear()

    def on_step(self) -> None:
        super().on_step()
        self._step_count += 1
        game_stats = self._sim.episode_stats.get("game", {})
        for key, value in game_stats.items():
            self._accumulated[key] += float(value)

    @property
    def time_averaged_game_stats(self) -> dict[str, float]:
        if self._step_count == 0:
            return {}
        return {k: v / self._step_count for k, v in self._accumulated.items()}
