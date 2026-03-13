import gc
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import contextmanager
from typing import Any, Iterator, Optional, Sequence

from mettagrid.config.mettagrid_config import MettaGridConfig
from mettagrid.envs.stats_tracker import StatsTracker
from mettagrid.policy.policy import AgentPolicy
from mettagrid.renderer.renderer import Renderer, RenderMode, create_renderer
from mettagrid.simulator.interface import SimulatorEventHandler
from mettagrid.simulator.policy_debug_projection import (
    compute_dialogue_transcript_update,
)
from mettagrid.simulator.simulator import Simulator
from mettagrid.types import Action
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
StepResult = tuple[int, Action, float, dict[str, Any], int, int]
_PENDING_RENDER_INTERVAL_SECONDS = 1.0 / 30.0


class _PendingRenderAborted(Exception):
    pass


class Rollout:
    """Run a multi-agent rollout over per-agent policies.

    `policies` is indexed per agent: `policies[i]` is the `AgentPolicy` used to
    step agent `i` for this rollout.

    `policy_group_keys`, when provided, is also indexed per agent and declares
    which agents share a backing policy service or other batching boundary. Agents
    with the same key may be stepped together via `can_step_group`/`step_group`;
    different groups may be dispatched in parallel.
    """

    def __init__(
        self,
        config: MettaGridConfig,
        policies: list[AgentPolicy],
        policy_names: Optional[Sequence[str]] = None,
        max_action_time_ms: int | None = 10000,
        overage_budget_ms: int | None = None,
        render_mode: Optional[RenderMode] = None,
        seed: int = 0,
        event_handlers: Optional[list[SimulatorEventHandler]] = None,
        stats_writer: Optional[StatsWriter] = None,
        autostart: bool = False,
        tracer: Optional[Tracer] = None,
        policy_group_keys: Sequence[object] | None = None,
    ):
        self._config = config
        self._policies = policies
        self._simulator = Simulator()
        self._max_action_time_ms: int = max_action_time_ms or 10000
        self._overage_remaining_ms: list[float] | None = (
            [float(overage_budget_ms)] * len(policies) if overage_budget_ms is not None else None
        )
        self._overage_exceeded_at: list[int | None] = [None] * len(policies)
        self._renderer: Optional[Renderer] = None
        self._render_initial_frame = render_mode in {"gui", "vibescope"}
        self._timeout_counts: list[int] = [0] * len(policies)
        self._tracer: Tracer = tracer or NullTracer()

        if policy_group_keys is not None and len(policy_group_keys) != len(policies):
            raise ValueError("policy_group_keys must have same length as policies")
        self._policy_group_keys = list(policy_group_keys) if policy_group_keys is not None else None
        self._policy_step_pool: ThreadPoolExecutor | None = None

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

        self._policy_names = (
            list(policy_names) if policy_names is not None else [type(policy).__name__ for policy in self._policies]
        )

        self._policy_infos: dict[int, dict] = {}
        self._dialogue_tail_by_agent: dict[int, str] = {}
        self._dialogue_updates: dict[int, dict[str, Any]] = {}
        self._step_count = 0
        self._skip_wait_on_policy_shutdown = False
        self._sim._context["policy_infos"] = self._policy_infos
        self._sim._context["dialogue_updates"] = self._dialogue_updates
        if self._renderer is not None and self._render_initial_frame:
            self._renderer.render()

    def step(self) -> None:
        """Execute one step of the rollout."""
        if self._step_count % 100 == 0:
            logger.debug(f"Step {self._step_count}")
        self._dialogue_updates.clear()

        try:
            if self._policy_group_keys is None:
                for i in range(len(self._policies)):
                    if self._overage_exceeded_at[i] is not None:
                        self._apply_disabled_action(i)
                        continue
                    self._step_single_index(i)
            else:
                # Group agents that share a batching boundary so each group can be
                # stepped together, while different groups can run concurrently.
                groups: dict[object, list[int]] = {}
                for i in range(len(self._policies)):
                    if self._overage_exceeded_at[i] is not None:
                        self._apply_disabled_action(i)
                        continue
                    group_key = self._policy_group_keys[i]
                    groups.setdefault(group_key, []).append(i)

                if groups:
                    group_steps = self._execute_group_steps(list(groups.values()))
                    # Apply results after worker execution so action setting, timeout
                    # accounting, and trace writes stay on the main rollout thread.
                    for (
                        index,
                        action,
                        elapsed_ms,
                        infos,
                        start_ns,
                        duration_ns,
                    ) in group_steps:
                        timed_out = self._apply_step_result(index, action, elapsed_ms, infos)
                        self._tracer.record_span(
                            "agent_step",
                            start_ns,
                            duration_ns,
                            agent=index,
                            step=self._step_count,
                            timed_out=timed_out,
                            elapsed_ms=elapsed_ms,
                        )
        except _PendingRenderAborted:
            return

        if self.is_done():
            return

        if self._renderer is not None:
            self._renderer.render()
        if self.is_done():
            return

        with self._tracer.span("env_step", step=self._step_count):
            self._sim.step()

        self._step_count += 1

    def run_until_done(self) -> None:
        """Run the rollout until completion or early exit."""
        try:
            while not self.is_done():
                with gc_disabled():
                    self.step()
        finally:
            if self._policy_step_pool is not None:
                self._policy_step_pool.shutdown(
                    wait=not self._skip_wait_on_policy_shutdown,
                    cancel_futures=True,
                )
                self._policy_step_pool = None
            self._tracer.flush()

    def is_done(self) -> bool:
        return self._sim.is_done()

    @property
    def timeout_counts(self) -> list[int]:
        """Return the timeout counts for each agent."""
        return self._timeout_counts

    @property
    def overage_exceeded_at(self) -> list[int | None]:
        """Return the step at which each agent's overage budget was exhausted, or None if never exceeded."""
        return self._overage_exceeded_at

    def _step_single_index(self, index: int) -> None:
        with self._tracer.span("agent_step", step=self._step_count, agent=index) as span:
            action, elapsed_ms, infos, _, _ = self._measure_single_step_with_pending_render(index)
            timed_out = self._apply_step_result(index, action, elapsed_ms, infos)
            span.set(timed_out=timed_out, elapsed_ms=elapsed_ms)

    def _execute_group_steps(
        self,
        group_indices: list[list[int]],
    ) -> list[StepResult]:
        if len(group_indices) == 1:
            return self._step_group(group_indices[0])

        # Multiple groups: dispatch in parallel across policy servers.
        if self._policy_step_pool is None:
            self._policy_step_pool = ThreadPoolExecutor(
                max_workers=max(1, min(len(group_indices), os.cpu_count() or 1))
            )
        futures = [self._policy_step_pool.submit(self._step_group, indices) for indices in group_indices]
        results: list[StepResult] = []
        for future in futures:
            results.extend(future.result())
        return results

    def _step_group(self, indices: list[int]) -> list[StepResult]:
        group_policies = [self._policies[index] for index in indices]
        first_policy = group_policies[0]
        if first_policy.can_step_group(group_policies):
            # A batched policy call returns one shared wall-clock duration for
            # every agent in the group.
            batch_observations = [(index, self._agents[index].observation) for index in indices]
            start_ns = time.time_ns()
            actions = first_policy.step_group(batch_observations)
            duration_ns = time.time_ns() - start_ns
            elapsed_ms = duration_ns / 1_000_000
            if len(actions) != len(indices):
                raise ValueError(f"step_group returned {len(actions)} actions for {len(indices)} agents")

            # Charge full wall-clock batch latency to each agent because all agents in
            # the group are blocked on the same remote policy-server round trip.
            # Note: infos are empty here because step_group is called on the first
            # policy only and does not update individual policy._infos.
            return [
                (index, actions[offset], elapsed_ms, {}, start_ns, duration_ns) for offset, index in enumerate(indices)
            ]

        return self._step_group_sequential(indices)

    def _step_group_sequential(self, indices: list[int]) -> list[StepResult]:
        # Reuse the single-agent measurement path when a group cannot be batched,
        # but defer mutation until the caller applies the collected results.
        group_results: list[StepResult] = []
        for index in indices:
            action, elapsed_ms, infos, start_ns, duration_ns = self._measure_single_step_with_pending_render(index)
            group_results.append((index, action, elapsed_ms, infos, start_ns, duration_ns))
        return group_results

    def _measure_single_step(self, index: int) -> tuple[Action, float, dict[str, Any], int, int]:
        # Pure measurement helper: no timeout accounting or rollout mutation.
        start_ns = time.time_ns()
        action = self._policies[index].step(self._agents[index].observation)
        duration_ns = time.time_ns() - start_ns
        elapsed_ms = duration_ns / 1_000_000
        infos = self._policies[index].infos
        merged_infos = dict(infos) if infos else {}
        return action, elapsed_ms, merged_infos, start_ns, duration_ns

    def _measure_single_step_with_pending_render(self, index: int) -> tuple[Action, float, dict[str, Any], int, int]:
        if self._renderer is None or not self._renderer.supports_pending_render():
            return self._measure_single_step(index)
        future = self._policy_executor().submit(self._measure_single_step, index)
        while True:
            try:
                return future.result(timeout=_PENDING_RENDER_INTERVAL_SECONDS)
            except TimeoutError as err:
                self._render_pending_frame()
                if self.is_done():
                    self._skip_wait_on_policy_shutdown = True
                    future.cancel()
                    raise _PendingRenderAborted from err

    def _apply_step_result(self, index: int, action: Action, elapsed_ms: float, infos: dict[str, Any]) -> bool:
        # Centralize the rollout-side effects so single and grouped paths stay aligned.
        action, timed_out = self._apply_timeout_budget(index, action, elapsed_ms)
        self._agents[index].set_action(action)
        self._update_policy_infos(index, infos)
        return timed_out

    def _apply_disabled_action(self, index: int) -> None:
        self._agents[index].set_action(self._config.game.actions.noop.Noop())
        if index < len(self._policy_names):
            self._policy_infos[index] = {"policy_name": self._policy_names[index]}

    def _apply_timeout_budget(self, index: int, action: Action, elapsed_ms: float) -> tuple[Action, bool]:
        overage_ms = max(0.0, elapsed_ms - self._max_action_time_ms)
        if overage_ms <= 0:
            return action, False

        logger.warning(f"Action took {elapsed_ms:.0f}ms, exceeding max of {self._max_action_time_ms}ms")
        self._timeout_counts[index] += 1
        if self._overage_remaining_ms is not None:
            self._overage_remaining_ms[index] -= overage_ms
            if self._overage_remaining_ms[index] <= 0:
                self._overage_exceeded_at[index] = self._step_count
                logger.warning(f"Agent {index} disabled at step {self._step_count} (overage budget exhausted)")
        return self._config.game.actions.noop.Noop(), True

    def _update_policy_infos(self, index: int, infos: dict[str, Any]) -> None:
        debug_infos = infos.pop("__sidecar_debug__", None)
        if isinstance(debug_infos, dict):
            self._update_dialogue_transcript(index, debug_infos)

        if index < len(self._policy_names):
            infos.setdefault("policy_name", self._policy_names[index])

        if infos:
            self._policy_infos[index] = infos
        else:
            self._policy_infos.pop(index, None)

    def _update_dialogue_transcript(self, index: int, debug_infos: dict[str, Any]) -> None:
        transcript_tail = debug_infos.get("transcript_tail")
        if not isinstance(transcript_tail, str) or not transcript_tail:
            return

        previous_tail = self._dialogue_tail_by_agent.get(index, "")
        dialogue_append, dialogue_reset = compute_dialogue_transcript_update(previous_tail, transcript_tail)
        self._dialogue_tail_by_agent[index] = transcript_tail
        if dialogue_append or dialogue_reset:
            self._dialogue_updates[index] = {
                "dialogue_append": dialogue_append,
                "dialogue_reset": dialogue_reset,
            }

    def _policy_executor(self) -> ThreadPoolExecutor:
        if self._policy_step_pool is None:
            self._policy_step_pool = ThreadPoolExecutor(max_workers=max(1, os.cpu_count() or 1))
        return self._policy_step_pool

    def _render_pending_frame(self) -> None:
        assert self._renderer is not None
        self._sim._context["policy_infos"] = self._policy_infos
        self._sim._context["dialogue_updates"] = self._dialogue_updates
        self._sim._context["allow_manual_actions"] = False
        try:
            self._renderer.render_pending()
        finally:
            self._sim._context["allow_manual_actions"] = True
