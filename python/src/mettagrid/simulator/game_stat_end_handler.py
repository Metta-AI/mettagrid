"""Simulation handler that ends episodes when game-stat thresholds are met."""

from __future__ import annotations

from mettagrid.simulator.interface import SimulatorEventHandler


class GameStatEndEpisodeHandler(SimulatorEventHandler):
    """End an episode when configured game stats reach target thresholds."""

    def __init__(self, thresholds: dict[str, float]):
        super().__init__()
        self._thresholds = dict(thresholds)
        self._triggered = False

    def on_episode_start(self) -> None:
        self._triggered = False

    def on_step(self) -> None:
        if self._triggered:
            return

        c_sim = self._sim._c_sim
        for stat_name, threshold in self._thresholds.items():
            value = c_sim.get_game_stat(stat_name)
            if value is None:
                continue
            value = float(value)
            threshold = float(threshold)
            if value < threshold:
                continue

            termination = self._sim._context.setdefault("termination", {})
            termination.update(
                {
                    "reason": "game_stat_threshold",
                    "stat": stat_name,
                    "threshold": threshold,
                    "value": value,
                }
            )
            self._sim.end_episode()
            self._triggered = True
            return
