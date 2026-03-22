"""Tests for cumulative overage budget in Rollout."""

import threading
import time

import mettagrid.simulator.rollout as rollout_module
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
from mettagrid.policy.policy import AgentPolicy, MultiAgentPolicy
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.renderer.renderer import Renderer
from mettagrid.runner.rollout import single_episode_rollout
from mettagrid.simulator.interface import AgentObservation
from mettagrid.simulator.rollout import Rollout
from mettagrid.types import Action


class SlowAgentPolicy(AgentPolicy):
    """Agent policy that sleeps for a configurable duration on each step."""

    def __init__(self, sleep_ms: float):
        self._sleep_ms = sleep_ms
        self._infos: dict = {}
        self.call_count = 0

    def step(self, obs: AgentObservation) -> Action:
        self.call_count += 1
        time.sleep(self._sleep_ms / 1000.0)
        return Action(name="noop")


class FastAgentPolicy(AgentPolicy):
    """Agent policy that returns instantly."""

    def __init__(self):
        self._infos: dict = {}
        self.call_count = 0

    def step(self, obs: AgentObservation) -> Action:
        self.call_count += 1
        return Action(name="noop")


class BarrierPolicy(AgentPolicy):
    def __init__(self, barrier: threading.Barrier):
        self._barrier = barrier
        self._infos: dict = {}
        self.call_count = 0

    def step(self, obs: AgentObservation) -> Action:
        _ = obs
        self.call_count += 1
        self._barrier.wait(timeout=1.0)
        return Action(name="noop")


class BatchGroupPolicy(AgentPolicy):
    def __init__(self):
        self._infos: dict = {}
        self.step_calls = 0
        self.step_group_calls = 0

    def step(self, obs: AgentObservation) -> Action:
        _ = obs
        self.step_calls += 1
        return Action(name="noop")

    def can_step_group(self, policies: list[AgentPolicy]) -> bool:
        return all(isinstance(policy, BatchGroupPolicy) for policy in policies)

    def step_group(self, observations: list[tuple[int, AgentObservation]]) -> list[Action]:
        self.step_group_calls += 1
        return [Action(name="noop") for _ in observations]


class RecordingRenderer(Renderer):
    def __init__(self):
        super().__init__()
        self.render_steps: list[int] = []

    def render(self) -> None:
        self.render_steps.append(self._sim.current_step)

    def on_episode_end(self) -> None:
        pass


class PendingMethodRenderer(Renderer):
    def __init__(self):
        super().__init__()
        self.pending_calls = 0
        self.render_calls = 0

    def supports_pending_render(self) -> bool:
        return True

    def render(self) -> None:
        self.render_calls += 1

    def render_pending(self) -> None:
        self.pending_calls += 1

    def on_episode_end(self) -> None:
        pass


class ClosingPendingRenderer(Renderer):
    def __init__(self):
        super().__init__()
        self.pending_calls = 0
        self.render_calls = 0

    def supports_pending_render(self) -> bool:
        return True

    def render(self) -> None:
        self.render_calls += 1

    def render_pending(self) -> None:
        self.pending_calls += 1
        self._sim.end_episode()

    def on_episode_end(self) -> None:
        pass


class PendingSlowPolicy(AgentPolicy):
    def __init__(self, sleep_ms: float = 50.0):
        self._sleep_ms = sleep_ms
        self._infos: dict = {}

    def step(self, obs: AgentObservation) -> Action:
        _ = obs
        time.sleep(self._sleep_ms / 1000.0)
        return Action(name="noop")


class NeverCompletingFuture:
    def __init__(self):
        self.cancel_calls = 0

    def result(self, timeout: float | None = None):  # type: ignore[no-untyped-def]
        _ = timeout
        raise rollout_module.TimeoutError

    def cancel(self) -> bool:
        self.cancel_calls += 1
        return False


class FakeExecutor:
    def __init__(self, future: NeverCompletingFuture):
        self._future = future
        self.shutdown_calls: list[tuple[bool, bool]] = []

    def submit(self, fn, *args, **kwargs):  # type: ignore[no-untyped-def]
        _ = (fn, args, kwargs)
        return self._future

    def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
        self.shutdown_calls.append((wait, cancel_futures))


class GroupStepFuture:
    def __init__(self, executor, fn, *args, **kwargs):  # type: ignore[no-untyped-def]
        self._executor = executor
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._released = False
        self._cancelled = False
        self._result = None
        self._error: Exception | None = None

    def release(self) -> None:
        if self._released or self._cancelled:
            return
        self._executor.submit_depth += 1
        try:
            self._result = self._fn(*self._args, **self._kwargs)
        except Exception as err:
            self._error = err
        finally:
            self._executor.submit_depth -= 1
        self._released = True

    def result(self, timeout: float | None = None):  # type: ignore[no-untyped-def]
        _ = timeout
        if not self._released:
            raise AssertionError("group future should not be consumed before the rollout wait loop releases it")
        if self._error is not None:
            raise self._error
        return self._result

    def cancel(self) -> bool:
        self._cancelled = True
        return True


class GroupStepExecutor:
    def __init__(self):
        self.submit_depth = 0
        self.nested_submit_attempts = 0
        self.submitted_futures: list[GroupStepFuture] = []

    def submit(self, fn, *args, **kwargs):  # type: ignore[no-untyped-def]
        if self.submit_depth > 0:
            self.nested_submit_attempts += 1
            raise AssertionError("group worker should not resubmit policy steps onto the same executor")
        future = GroupStepFuture(self, fn, *args, **kwargs)
        self.submitted_futures.append(future)
        return future

    def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
        _ = (wait, cancel_futures)


def _make_config(num_agents: int = 2, max_steps: int = 10) -> MettaGridConfig:
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


def test_overage_depletes_and_disables():
    """Policy that exceeds max_action_time_ms each step gets disabled after budget exhaustion."""
    max_action_time_ms = 10  # 10ms limit
    overage_per_step_ms = 20  # each step takes ~30ms total, 20ms overage
    overage_budget_ms = 35  # budget exhausted after 2 overages (20+20 > 35)
    config = _make_config(num_agents=1, max_steps=10)

    slow_policy = SlowAgentPolicy(sleep_ms=max_action_time_ms + overage_per_step_ms)
    rollout = Rollout(
        config,
        [slow_policy],
        max_action_time_ms=max_action_time_ms,
        overage_budget_ms=overage_budget_ms,
    )
    rollout.run_until_done()

    # Policy should have been disabled before all 10 steps completed
    assert slow_policy.call_count < 10
    assert rollout.overage_exceeded_at[0] is not None
    assert rollout.overage_exceeded_at[0] < 10  # disabled before max_steps
    assert rollout.timeout_counts[0] >= 2


def test_fast_policy_never_disabled():
    """Policy that never times out is never disabled."""
    config = _make_config(num_agents=1, max_steps=5)

    fast_policy = FastAgentPolicy()
    rollout = Rollout(
        config,
        [fast_policy],
        max_action_time_ms=10000,
        overage_budget_ms=100,
    )
    rollout.run_until_done()

    assert fast_policy.call_count == 5
    assert rollout.overage_exceeded_at[0] is None
    assert rollout.timeout_counts[0] == 0


def test_none_budget_preserves_behavior():
    """With overage_budget_ms=None, timeouts still noop but policy is never disabled."""
    max_action_time_ms = 10
    config = _make_config(num_agents=1, max_steps=5)

    slow_policy = SlowAgentPolicy(sleep_ms=max_action_time_ms + 20)
    rollout = Rollout(
        config,
        [slow_policy],
        max_action_time_ms=max_action_time_ms,
        overage_budget_ms=None,
    )
    rollout.run_until_done()

    # All 5 steps should call the policy (no permanent disable)
    assert slow_policy.call_count == 5
    assert rollout.overage_exceeded_at[0] is None
    assert rollout.timeout_counts[0] == 5


def test_partial_depletion_does_not_disable():
    """Agent that times out but doesn't exhaust budget stays active."""
    max_action_time_ms = 10
    overage_per_step_ms = 15  # each timeout costs ~15ms overage
    overage_budget_ms = 500  # large budget — never exhausted in 5 steps
    config = _make_config(num_agents=1, max_steps=5)

    slow_policy = SlowAgentPolicy(sleep_ms=max_action_time_ms + overage_per_step_ms)
    rollout = Rollout(
        config,
        [slow_policy],
        max_action_time_ms=max_action_time_ms,
        overage_budget_ms=overage_budget_ms,
    )
    rollout.run_until_done()

    # All 5 steps should call the policy — budget not exhausted
    assert slow_policy.call_count == 5
    assert rollout.overage_exceeded_at[0] is None
    assert rollout.timeout_counts[0] == 5


def test_overage_exceeded_at_reported_in_results():
    """overage_exceeded_at in PureSingleEpisodeResult matches rollout.overage_exceeded_at."""
    max_action_time_ms = 10
    overage_budget_ms = 15

    class _SlowMultiPolicy(MultiAgentPolicy):
        def agent_policy(self, agent_id: int) -> AgentPolicy:
            return SlowAgentPolicy(sleep_ms=max_action_time_ms + 20)

    config = _make_config(num_agents=2, max_steps=5)
    env_interface = PolicyEnvInterface.from_mg_cfg(config)
    policy = _SlowMultiPolicy(env_interface)

    results, _ = single_episode_rollout(
        [policy],
        [0, 0],
        config,
        seed=42,
        max_action_time_ms=max_action_time_ms,
        overage_budget_ms=overage_budget_ms,
        render_mode="none",
        autostart=False,
        capture_replay=False,
    )

    # Both agents use the same slow policy, both should have been disabled
    assert results.overage_exceeded_at is not None
    assert len(results.overage_exceeded_at) == 2
    assert all(step is not None for step in results.overage_exceeded_at)


def test_disabled_agent_still_sets_policy_name():
    """Disabled agents still populate policy_infos with policy_name for renderers."""
    max_action_time_ms = 10
    # Budget of 1ms: first overage (20ms) will exhaust it immediately
    overage_budget_ms = 1
    config = _make_config(num_agents=1, max_steps=5)

    slow_policy = SlowAgentPolicy(sleep_ms=max_action_time_ms + 20)
    rollout = Rollout(
        config,
        [slow_policy],
        policy_names=["test_policy"],
        max_action_time_ms=max_action_time_ms,
        overage_budget_ms=overage_budget_ms,
    )

    # Run enough steps for the policy to be disabled, then check infos
    for _ in range(5):
        if rollout.is_done():
            break
        rollout.step()

    assert rollout.overage_exceeded_at[0] is not None
    # After disabling, policy_infos should still have the policy_name
    assert 0 in rollout._policy_infos
    assert rollout._policy_infos[0]["policy_name"] == "test_policy"


def test_parallel_policy_groups_execute_concurrently():
    config = _make_config(num_agents=2, max_steps=1)
    barrier = threading.Barrier(2)

    policy_0 = BarrierPolicy(barrier)
    policy_1 = BarrierPolicy(barrier)

    rollout = Rollout(
        config,
        [policy_0, policy_1],
        max_action_time_ms=10_000,
        policy_group_keys=[0, 1],
    )
    rollout.step()

    assert policy_0.call_count == 1
    assert policy_1.call_count == 1


def test_group_step_uses_batch_path_when_available():
    config = _make_config(num_agents=2, max_steps=1)
    policy_0 = BatchGroupPolicy()
    policy_1 = BatchGroupPolicy()

    rollout = Rollout(
        config,
        [policy_0, policy_1],
        max_action_time_ms=10_000,
        policy_group_keys=[0, 0],
    )
    rollout.step()

    assert policy_0.step_group_calls == 1
    assert policy_0.step_calls == 0
    assert policy_1.step_calls == 0


def test_group_step_does_not_reuse_stale_agent_infos():
    config = _make_config(num_agents=2, max_steps=1)
    policy_0 = BatchGroupPolicy()
    policy_1 = BatchGroupPolicy()
    policy_0._infos = {"stale": "old"}
    policy_1._infos = {"stale": "old"}

    rollout = Rollout(
        config,
        [policy_0, policy_1],
        policy_names=["policy_0", "policy_1"],
        max_action_time_ms=10_000,
        policy_group_keys=[0, 0],
    )
    rollout.step()

    assert rollout._policy_infos[0] == {"policy_name": "policy_0"}
    assert rollout._policy_infos[1] == {"policy_name": "policy_1"}


def test_rollout_renders_initial_gui_frame_before_first_policy_step(
    monkeypatch,
) -> None:
    config = _make_config(num_agents=1, max_steps=1)
    renderer = RecordingRenderer()
    monkeypatch.setattr(rollout_module, "create_renderer", lambda *args, **kwargs: renderer)

    policy = FastAgentPolicy()
    rollout = Rollout(
        config,
        [policy],
        max_action_time_ms=10_000,
        render_mode="gui",
    )

    assert renderer.render_steps == [0]
    assert policy.call_count == 0
    assert rollout._sim.current_step == 0


def test_rollout_uses_pending_render_hook_while_policy_step_is_running(
    monkeypatch,
) -> None:
    config = _make_config(num_agents=1, max_steps=1)
    renderer = PendingMethodRenderer()
    monkeypatch.setattr(rollout_module, "create_renderer", lambda *args, **kwargs: renderer)

    rollout = Rollout(
        config,
        [PendingSlowPolicy()],
        policy_names=["pending_policy"],
        max_action_time_ms=10_000,
        render_mode="gui",
    )

    rollout.step()

    assert renderer.pending_calls > 0
    assert renderer.render_calls >= 1


def test_rollout_pending_close_aborts_blocked_step_without_waiting_for_policy_shutdown(
    monkeypatch,
) -> None:
    config = _make_config(num_agents=1, max_steps=5)
    renderer = ClosingPendingRenderer()
    monkeypatch.setattr(rollout_module, "create_renderer", lambda *args, **kwargs: renderer)

    rollout = Rollout(
        config,
        [FastAgentPolicy()],
        max_action_time_ms=10_000,
        render_mode="gui",
    )
    future = NeverCompletingFuture()
    executor = FakeExecutor(future)
    rollout._policy_step_pool = executor  # type: ignore[assignment]

    rollout.run_until_done()

    assert renderer.render_calls == 1
    assert renderer.pending_calls == 1
    assert future.cancel_calls == 1
    assert executor.shutdown_calls == [(False, True)]
    assert rollout.is_done() is True
    assert rollout._sim.current_step == 0


def test_rollout_group_pending_render_waits_on_main_thread_without_nested_submit(
    monkeypatch,
) -> None:
    config = _make_config(num_agents=2, max_steps=1)
    renderer = PendingMethodRenderer()
    monkeypatch.setattr(rollout_module, "create_renderer", lambda *args, **kwargs: renderer)

    rollout = Rollout(
        config,
        [FastAgentPolicy(), FastAgentPolicy()],
        max_action_time_ms=10_000,
        render_mode="gui",
        policy_group_keys=["group-0", "group-1"],
    )
    executor = GroupStepExecutor()
    rollout._policy_step_pool = executor  # type: ignore[assignment]

    wait_calls = 0

    def fake_wait(futures, timeout=None):  # type: ignore[no-untyped-def]
        _ = timeout
        nonlocal wait_calls
        wait_calls += 1
        future_list = list(futures)
        if wait_calls == 1:
            return set(), set(future_list)
        for future in future_list:
            future.release()
        return set(future_list), set()

    monkeypatch.setattr(rollout_module, "wait", fake_wait)

    rollout.step()

    assert wait_calls == 2
    assert executor.nested_submit_attempts == 0
    assert renderer.pending_calls == 1
    assert renderer.render_calls == 1
