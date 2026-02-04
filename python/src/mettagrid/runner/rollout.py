import logging
import random
import uuid
from pathlib import Path
from typing import Callable, Optional, Protocol, Sequence

from mettagrid import MettaGridConfig
from mettagrid.policy.loader import AgentPolicy, PolicyEnvInterface, initialize_or_load_policy
from mettagrid.policy.policy import MultiAgentPolicy, PolicySpec
from mettagrid.renderer.renderer import RenderMode
from mettagrid.runner.pure_single_episode_runner import (
    PureSingleEpisodeJob,
    PureSingleEpisodeResult,
    _validate_assignments,
    _validate_output_uri,
)
from mettagrid.runner.remote import PolicyStepError, RemoteMultiAgentPolicy
from mettagrid.simulator.multi_episode.rollout import EpisodeRolloutResult, MultiEpisodeRolloutResult
from mettagrid.simulator.replay_log_writer import EpisodeReplay, InMemoryReplayWriter
from mettagrid.simulator.rollout import Rollout
from mettagrid.util.file import write_data
from mettagrid.util.tracer import Tracer

logger = logging.getLogger(__name__)


def _setup_trace_path(debug_dir: Optional[str]) -> Optional[Path]:
    if debug_dir is None:
        return None
    debug_path = Path(debug_dir)
    debug_path.mkdir(parents=True, exist_ok=True)
    return debug_path / "trace.json"


class ReplayLike(Protocol):
    def set_compression(self, compression: str) -> None: ...

    def write_replay(self, path: str) -> None: ...


def write_replay(replay: ReplayLike, path: str) -> None:
    if path.endswith(".gz"):
        replay.set_compression("gzip")
    elif path.endswith(".z"):
        replay.set_compression("zlib")
    replay.write_replay(path)


def _remote_policies_from_uris(
    policy_uris: Sequence[str],
    env_interface: PolicyEnvInterface,
) -> list[RemoteMultiAgentPolicy]:
    return [RemoteMultiAgentPolicy(env_interface, base_url=uri) for uri in policy_uris]


def _write_outputs(
    results: PureSingleEpisodeResult,
    replay: Optional[EpisodeReplay],
    *,
    results_uri: Optional[str],
    replay_uri: Optional[str],
) -> None:
    if replay_uri is not None:
        if replay is None:
            raise ValueError("No replay was generated")
        write_replay(replay, replay_uri)
    if results_uri is not None:
        write_data(results_uri, results.model_dump_json(), content_type="application/json")


def _run_pure_episode(
    policies: Sequence[MultiAgentPolicy],
    assignments: Sequence[int],
    env: MettaGridConfig,
    *,
    seed: int,
    max_action_time_ms: int,
    render_mode: RenderMode,
    autostart: bool,
    capture_replay: bool,
    trace_path: Optional[Path] = None,
) -> tuple[PureSingleEpisodeResult, Optional[EpisodeReplay]]:
    agent_policies: list[AgentPolicy] = [
        policies[assignment].agent_policy(agent_id) for agent_id, assignment in enumerate(assignments)
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
        max_action_time_ms=max_action_time_ms,
        render_mode=render_mode,
        autostart=autostart,
        seed=seed,
        event_handlers=[replay_writer] if replay_writer is not None else None,
        tracer=tracer,
    )
    rollout.run_until_done()

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


def _policies_from_specs(
    policy_specs: Sequence[PolicySpec],
    env_interface: PolicyEnvInterface,
    device: Optional[str],
) -> list[MultiAgentPolicy]:
    return [initialize_or_load_policy(env_interface, spec, device_override=device) for spec in policy_specs]


def run_single_episode(
    *,
    policy_specs: Sequence[PolicySpec],
    assignments: Sequence[int],
    env: MettaGridConfig,
    results_uri: Optional[str] = None,
    replay_uri: Optional[str] = None,
    debug_dir: Optional[str] = None,
    seed: int = 0,
    max_action_time_ms: int = 10000,
    device: Optional[str] = None,
    render_mode: Optional[RenderMode] = None,
    autostart: bool = False,
) -> tuple[PureSingleEpisodeResult, Optional[EpisodeReplay]]:
    _validate_assignments(assignments, env.game.num_agents, len(policy_specs))

    for uri in (replay_uri, results_uri):
        if uri is None:
            continue
        _validate_output_uri(uri)

    if replay_uri is not None and not replay_uri.endswith((".json.z", ".json.gz")):
        raise ValueError("Replay URI must end with .json.z or .json.gz")

    trace_path = _setup_trace_path(debug_dir)

    env_interface = PolicyEnvInterface.from_mg_cfg(env)
    policies = _policies_from_specs(policy_specs, env_interface, device)

    results, replay = _run_pure_episode(
        policies,
        assignments,
        env,
        seed=seed,
        max_action_time_ms=max_action_time_ms,
        render_mode=render_mode or "none",
        autostart=autostart,
        capture_replay=replay_uri is not None,
        trace_path=trace_path,
    )

    _write_outputs(results, replay, results_uri=results_uri, replay_uri=replay_uri)
    return results, replay


def run_sandboxed_episode(
    job: PureSingleEpisodeJob,
    *,
    render_mode: Optional[RenderMode] = None,
) -> tuple[PureSingleEpisodeResult, Optional[EpisodeReplay]]:
    env_interface = PolicyEnvInterface.from_mg_cfg(job.env)
    policies = _remote_policies_from_uris(job.policy_uris, env_interface)
    trace_path = _setup_trace_path(job.debug_dir)

    try:
        results, replay = _run_pure_episode(
            policies,
            job.assignments,
            job.env,
            seed=job.seed,
            max_action_time_ms=job.max_action_time_ms,
            render_mode=render_mode or "none",
            autostart=False,
            capture_replay=job.replay_uri is not None,
            trace_path=trace_path,
        )
    except PolicyStepError:
        logger.error("Policy server failed during episode execution", exc_info=True)
        raise
    finally:
        for p in policies:
            p.close()

    _write_outputs(results, replay, results_uri=job.results_uri, replay_uri=job.replay_uri)
    return results, replay


def run_single_episode_rollout(
    *,
    policy_specs: Sequence[PolicySpec],
    assignments: Sequence[int],
    env_cfg: MettaGridConfig,
    seed: int,
    max_action_time_ms: int,
    replay_path: Optional[str] = None,
    device: Optional[str] = None,
) -> EpisodeRolloutResult:
    results, _replay = run_single_episode(
        policy_specs=policy_specs,
        assignments=list(assignments),
        env=env_cfg,
        results_uri=None,
        replay_uri=replay_path,
        seed=seed,
        max_action_time_ms=max_action_time_ms,
        device=device,
    )

    return EpisodeRolloutResult(
        assignments=list(assignments),
        rewards=list(results.rewards),
        action_timeouts=list(results.action_timeouts),
        stats=results.stats,
        replay_path=replay_path,
        steps=results.steps,
        max_steps=env_cfg.game.max_steps,
    )


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
    if replay_dir is not None and create_replay_dir:
        Path(replay_dir).mkdir(parents=True, exist_ok=True)

    assignments_list = list(assignments)
    rng = rng or random.Random(seed)
    episode_results: list[EpisodeRolloutResult] = []
    replay_paths: list[str] = []

    for episode_idx in range(episodes):
        rng.shuffle(assignments_list)
        replay_path = None
        if replay_dir is not None:
            replay_path = str(Path(replay_dir) / f"{uuid.uuid4()}.json.z")

        result = run_single_episode_rollout(
            policy_specs=policy_specs,
            assignments=assignments_list,
            env_cfg=env_cfg,
            seed=seed + episode_idx,
            max_action_time_ms=max_action_time_ms,
            replay_path=replay_path,
            device=device,
        )
        episode_results.append(result)
        if on_progress:
            on_progress(episode_idx, result)
        if replay_path is not None:
            replay_paths.append(replay_path)

    return MultiEpisodeRolloutResult(episodes=episode_results), replay_paths
