import numpy as np

from mettagrid.simulator import SimulatorEventHandler


class EarlyResetHandler(SimulatorEventHandler):
    def __init__(self):
        super().__init__()
        self._should_early_reset: bool = True
        self._early_reset_step: int | None = None

    def on_episode_start(self) -> None:
        if self._should_early_reset:
            self._should_early_reset = False
            # Avoid global NumPy RNG state (fork inherits it on Linux).
            rng = np.random.default_rng(self._sim.seed)
            self._early_reset_step = int(rng.integers(1, self._sim.config.game.max_steps + 1))

    def on_step(self) -> None:
        if self._early_reset_step is not None and self._sim.current_step >= self._early_reset_step:
            self._sim.end_episode()
            self._early_reset_step = None
