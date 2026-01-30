import gc
import logging
import time
from contextlib import contextmanager
from typing import Iterator, Optional

from mettagrid.config.mettagrid_config import MettaGridConfig
from mettagrid.envs.stats_tracker import StatsTracker
from mettagrid.policy.policy import AgentPolicy
from mettagrid.renderer.renderer import Renderer, RenderMode, create_renderer
from mettagrid.simulator.interface import SimulatorEventHandler
from mettagrid.simulator.simulator import Simulator
from mettagrid.util.stats_writer import StatsWriter
from mettagrid.util.tracer import NullTracer, Tracer


@contextmanager
def gc_disabled() -> Iterator[None]:
    """Disable GC for a latency-sensitive section, then allow it to run if needed.

    Gen2 collections take ~100ms, which is large compared to our per-policy-step
    timeouts. This context manager disables GC during the critical section, then
    on exit allows GC to run if thresholds are met (without forcing a full
    collection).
    """
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        yield
    finally:
        if was_enabled:
            gc.enable()
            _ = []  # Allocate a container to trigger GC threshold evaluation


logger = logging.getLogger(__name__)


class Rollout:
    """Rollout class for running a multi-agent policy rollout."""

    def __init__(
        self,
        config: MettaGridConfig,
        policies: list[AgentPolicy],
        max_action_time_ms: int | None = 10000,
        render_mode: Optional[RenderMode] = None,
        seed: int = 0,
        event_handlers: Optional[list[SimulatorEventHandler]] = None,
        stats_writer: Optional[StatsWriter] = None,
        autostart: bool = False,
        tracer: Optional[Tracer] = None,
    ):
        self._config = config
        self._policies = policies
        self._simulator = Simulator()
        self._max_action_time_ms: int = max_action_time_ms or 10000
        self._renderer: Optional[Renderer] = None
        self._timeout_counts: list[int] = [0] * len(policies)
        self._tracer: Tracer = tracer or NullTracer()
        # Attach renderer if specified
        if render_mode is not None:
            self._renderer = create_renderer(render_mode, autostart=autostart)
            self._simulator.add_event_handler(self._renderer)
        # Attach stats tracker if provided
        if stats_writer is not None:
            self._simulator.add_event_handler(StatsTracker(stats_writer))
        # Attach additional event handlers
        for handler in event_handlers or []:
            self._simulator.add_event_handler(handler)
        self._sim = self._simulator.new_simulation(config, seed)
        self._agents = self._sim.agents()

        # Add pointer to policies so that Doxascope EventHandlers can access:
        self._sim._context["policies"] = self._policies

        # Reset policies and create agent policies if needed
        for policy in self._policies:
            policy.reset()

        self._step_count = 0

    def step(self) -> None:
        """Execute one step of the rollout."""
        if self._step_count % 100 == 0:
            logger.debug(f"Step {self._step_count}")

        for i in range(len(self._policies)):
            with self._tracer.span("agent_step", step=self._step_count, agent=i) as span:
                start_time = time.time()
                action = self._policies[i].step(self._agents[i].observation)
                elapsed_ms = (time.time() - start_time) * 1000
                timed_out = elapsed_ms > self._max_action_time_ms
                if timed_out:
                    logger.warning(f"Action took {elapsed_ms}ms, exceeding max of {self._max_action_time_ms}ms")
                    action = self._config.game.actions.noop.Noop()
                    self._timeout_counts[i] += 1
                span.set(timed_out=timed_out)
            self._agents[i].set_action(action)

        if self._renderer is not None:
            self._renderer.render()

        with self._tracer.span("env_step", step=self._step_count):
            self._sim.step()

        self._step_count += 1

    def run_until_done(self) -> None:
        """Run the rollout until completion or early exit."""
        while not self.is_done():
            with gc_disabled():
                self.step()
        self._tracer.flush()

    def is_done(self) -> bool:
        return self._sim.is_done()

    @property
    def timeout_counts(self) -> list[int]:
        """Return the timeout counts for each agent."""
        return self._timeout_counts
