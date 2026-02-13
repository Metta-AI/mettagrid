import logging
import random
import uuid
from pathlib import Path
from typing import Callable, Optional, Sequence

from mettagrid import MettaGridConfig
from mettagrid.policy.loader import AgentPolicy, PolicyEnvInterface, initialize_or_load_policy
from mettagrid.policy.policy import MultiAgentPolicy, PolicySpec
from mettagrid.renderer.renderer import RenderMode
from mettagrid.runner.types import PureSingleEpisodeResult
from mettagrid.simulator.multi_episode.rollout import EpisodeRolloutResult, MultiEpisodeRolloutResult
from mettagrid.simulator.replay_log_writer import EpisodeReplay, InMemoryReplayWriter
from mettagrid.simulator.rollout import Rollout
from mettagrid.util.file import write_data
from mettagrid.util.tracer import Tracer

logger = logging.getLogger(__name__)


def _policy_display_name(policy: MultiAgentPolicy, fallback: str) -> str:
    name = getattr(policy, "_policy_name", None)
    if isinstance(name, str) and name:
        return name
    return fallback


def single_episode_rollout(
    policies: Sequence[MultiAgentPolicy],
    assignments: Sequence[int],
    env: MettaGridConfig,
    *,
    seed: int,
    max_action_time_ms: int,
    render_mode: RenderMode,
    autostart: bool,
    capture_replay: bool,
    policy_names: Optional[Sequence[str]] = None,
    trace_path: Optional[Path] = None,
) -> tuple[PureSingleEpisodeResult, Optional[EpisodeReplay]]:
    """Run a single episode in-process using already-instantiated policy objects.

    This is the core simulation loop. No I/O, no subprocess, no policy loading --
    just policies + env config in, results out. Used by both run_episode_local
    (which loads policies itself) and the subprocess entry point in
    episode_subprocess (which receives policies over HTTP).
    """
    agent_policies: list[AgentPolicy] = [
        policies[assignment].agent_policy(agent_id) for agent_id, assignment in enumerate(assignments)
    ]
    if policy_names is not None:
        if len(policy_names) != len(policies):
            raise ValueError("policy_names must have the same length as policies")
        agent_policy_names = [policy_names[assignment] for assignment in assignments]
    else:
        agent_policy_names = [
            _policy_display_name(
                policies[assignment],
                fallback=f"policy_{assignment}",
            )
            for assignment in assignments
        ]
    replay_writer: Optional[InMemoryReplayWriter] = None
    if capture_replay:
        replay_writer = InMemoryReplayWriter()

    tracer: Optional[Tracer] = None
    if trace_path:
        tracer = Tracer(trace_path)

    rollout = Rollout(
        env,
        agent_policies,
        policy_names=agent_policy_names,
        max_action_time_ms=max_action_time_ms,
        render_mode=render_mode,
        autostart=autostart,
        seed=seed,
        event_handlers=[replay_writer] if replay_writer is not None else None,
        tracer=tracer,
    )
    rollout.run_until_done()

    if tracer:
        tracer.flush()

    results = PureSingleEpisodeResult(
        rewards=list(rollout._sim.episode_rewards),
        action_timeouts=list(rollout.timeout_counts),
        stats=rollout._sim.episode_stats,
        steps=rollout._sim.current_step,
    )
    replay: Optional[EpisodeReplay] = None
    if replay_writer is not None:
        replays = replay_writer.get_completed_replays()
        if len(replays) != 1:
            raise ValueError(f"Expected 1 replay, got {len(replays)}")
        replay = replays[0]

    return results, replay


def run_episode_local(
    *,
    policy_specs: Sequence[PolicySpec],
    assignments: Sequence[int],
    env: MettaGridConfig,
    results_path: Path | None = None,
    replay_path: Path | None = None,
    debug_dir: Path | None = None,
    seed: int = 0,
    max_action_time_ms: int = 10000,
    device: Optional[str] = None,
    render_mode: Optional[RenderMode] = None,
    autostart: bool = False,
) -> tuple[PureSingleEpisodeResult, Optional[EpisodeReplay]]:
    """Run a single episode in the current process, loading policies from PolicySpecs.

    Policies are loaded directly (via initialize_or_load_policy), so this only works
    when the policy code and weights are available locally. Supports rendering and
    interactive play. For running untrusted or remote policies in a subprocess, use
    run_episode_isolated instead.
    """
    if len(assignments) != env.game.num_agents or not all(0 <= a < len(policy_specs) for a in assignments):
        raise ValueError("Assignments must match agent count and be within policy range")

    trace_path: Path | None = None
    if debug_dir is not None:
        debug_dir.mkdir(parents=True, exist_ok=True)
        trace_path = debug_dir / "trace.json"

    env_interface = PolicyEnvInterface.from_mg_cfg(env)
    policies = [initialize_or_load_policy(env_interface, spec, device_override=device) for spec in policy_specs]
    policy_names = [policy_spec.name for policy_spec in policy_specs]

    results, replay = single_episode_rollout(
        policies,
        assignments,
        env,
        seed=seed,
        max_action_time_ms=max_action_time_ms,
        render_mode=render_mode or "none",
        autostart=autostart,
        capture_replay=replay_path is not None,
        policy_names=policy_names,
        trace_path=trace_path,
    )

    if replay_path is not None:
        if replay is None:
            raise ValueError("No replay was generated")
        replay.write_replay(replay_path.resolve().as_uri())
    if results_path is not None:
        write_data(results_path.resolve().as_uri(), results.model_dump_json(), content_type="application/json")

    return results, replay


def run_multi_episode_rollout(
    *,
    policy_specs: Sequence[PolicySpec],
    assignments: Sequence[int],
    env_cfg: MettaGridConfig,
    episodes: int,
    seed: int,
    max_action_time_ms: int,
    replay_dir: Optional[str | Path] = None,
    create_replay_dir: bool = False,
    rng: Optional[random.Random] = None,
    device: Optional[str] = None,
    on_progress: Optional[Callable[[int, EpisodeRolloutResult], None]] = None,
) -> tuple[MultiEpisodeRolloutResult, list[str]]:
    if replay_dir is not None:
        if create_replay_dir:
            Path(replay_dir).mkdir(parents=True, exist_ok=True)
        elif not Path(replay_dir).is_dir():
            raise ValueError(f"Replay directory does not exist: {replay_dir}")

    assignments_list = list(assignments)
    rng = rng or random.Random(seed)
    episode_results: list[EpisodeRolloutResult] = []
    replay_paths: list[str] = []

    for episode_idx in range(episodes):
        rng.shuffle(assignments_list)
        replay_path: Path | None = None
        if replay_dir is not None:
            replay_path = Path(replay_dir) / f"{uuid.uuid4()}.json.z"

        ep_results, _replay = run_episode_local(
            policy_specs=policy_specs,
            assignments=list(assignments_list),
            env=env_cfg,
            results_path=None,
            replay_path=replay_path,
            seed=seed + episode_idx,
            max_action_time_ms=max_action_time_ms,
            device=device,
        )
        result = EpisodeRolloutResult(
            assignments=list(assignments_list),
            rewards=list(ep_results.rewards),
            action_timeouts=list(ep_results.action_timeouts),
            stats=ep_results.stats,
            replay_path=str(replay_path) if replay_path else None,
            steps=ep_results.steps,
            max_steps=env_cfg.game.max_steps,
        )
        episode_results.append(result)
        if on_progress:
            on_progress(episode_idx, result)
        if replay_path is not None:
            replay_paths.append(str(replay_path))

    return MultiEpisodeRolloutResult(episodes=episode_results), replay_paths
