import json
import random
import socket
import sys
import uuid
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Callable, Optional, Protocol, Sequence

from mettagrid import MettaGridConfig
from mettagrid.policy.loader import AgentPolicy, PolicyEnvInterface, initialize_or_load_policy
from mettagrid.policy.policy import PolicySpec
from mettagrid.renderer.renderer import RenderMode
from mettagrid.runner.pure_single_episode_runner import (
    PureSingleEpisodeJob,
    PureSingleEpisodeResult,
    _validate_assignments,
    _validate_output_uri,
)
from mettagrid.simulator.multi_episode.rollout import EpisodeRolloutResult, MultiEpisodeRolloutResult
from mettagrid.simulator.replay_log_writer import EpisodeReplay, InMemoryReplayWriter
from mettagrid.simulator.rollout import Rollout
from mettagrid.util.file import write_data
from mettagrid.util.tracer import Tracer
from mettagrid.util.uri_resolvers.schemes import parse_uri, policy_spec_from_uri


class ReplayLike(Protocol):
    def set_compression(self, compression: str) -> None: ...

    def write_replay(self, path: str) -> None: ...


def write_replay(replay: ReplayLike, path: str) -> None:
    if path.endswith(".gz"):
        replay.set_compression("gzip")
    elif path.endswith(".z"):
        replay.set_compression("zlib")
    replay.write_replay(path)


@contextmanager
def _no_python_sockets():
    _real_socket = socket.socket
    _real_getaddrinfo = socket.getaddrinfo

    def _blocked(*args: object, **kwargs: object):
        raise RuntimeError("Network access disabled")

    socket.socket = _blocked
    socket.getaddrinfo = _blocked

    try:
        yield
    finally:
        socket.socket = _real_socket
        socket.getaddrinfo = _real_getaddrinfo


def _policy_specs_from_uris(
    policy_uris: Sequence[str],
    *,
    device: Optional[str],
    allow_network: bool,
) -> list[PolicySpec]:
    policy_specs: list[PolicySpec] = []
    for uri in policy_uris:
        parsed = parse_uri(uri, allow_none=False)
        if parsed.scheme != "file" and not allow_network:
            raise ValueError("Sandboxed runner requires file:// policy URIs")
        policy_specs.append(
            policy_spec_from_uri(
                uri,
                device=device or "cpu",
                remove_downloaded_copy_on_exit=True,
            )
        )
    return policy_specs


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
    policy_specs: Sequence[PolicySpec],
    assignments: Sequence[int],
    env: MettaGridConfig,
    *,
    seed: int,
    max_action_time_ms: int,
    device: Optional[str],
    render_mode: RenderMode,
    autostart: bool,
    capture_replay: bool,
    trace_path: Optional[Path] = None,
) -> tuple[PureSingleEpisodeResult, Optional[EpisodeReplay]]:
    env_interface = PolicyEnvInterface.from_mg_cfg(env)
    agent_policies: list[AgentPolicy] = [
        initialize_or_load_policy(
            env_interface,
            policy_specs[assignment],
            device_override=device,
        ).agent_policy(agent_id)
        for agent_id, assignment in enumerate(assignments)
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
    allow_network: bool = True,
) -> tuple[PureSingleEpisodeResult, Optional[EpisodeReplay]]:
    _validate_assignments(assignments, env.game.num_agents, len(policy_specs))

    for uri in (replay_uri, results_uri):
        if uri is None:
            continue
        _validate_output_uri(uri)

    if replay_uri is not None and not replay_uri.endswith((".json.z", ".json.gz")):
        raise ValueError("Replay URI must end with .json.z or .json.gz")

    trace_path: Optional[Path] = None
    if debug_dir is not None:
        debug_path = Path(debug_dir)
        debug_path.mkdir(parents=True, exist_ok=True)
        trace_path = debug_path / "trace.json"

    with (_no_python_sockets if not allow_network else nullcontext)():
        results, replay = _run_pure_episode(
            policy_specs,
            assignments,
            env,
            seed=seed,
            max_action_time_ms=max_action_time_ms,
            device=device,
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
    device: Optional[str] = None,
    render_mode: Optional[RenderMode] = None,
) -> tuple[PureSingleEpisodeResult, Optional[EpisodeReplay]]:
    policy_specs = _policy_specs_from_uris(job.policy_uris, device=device, allow_network=False)
    return run_single_episode(
        policy_specs=policy_specs,
        assignments=job.assignments,
        env=job.env,
        results_uri=job.results_uri,
        replay_uri=job.replay_uri,
        debug_dir=job.debug_dir,
        seed=job.seed,
        max_action_time_ms=job.max_action_time_ms,
        device=device,
        render_mode=render_mode,
        allow_network=False,
    )


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


if __name__ == "__main__":
    with open(sys.argv[1]) as f:
        args = json.load(f)
    job = PureSingleEpisodeJob.model_validate(args["job"])
    device = args.get("device")
    allow_network = args.get("allow_network", False)
    policy_specs = _policy_specs_from_uris(job.policy_uris, device=device, allow_network=allow_network)
    run_single_episode(
        policy_specs=policy_specs,
        assignments=job.assignments,
        env=job.env,
        results_uri=job.results_uri,
        replay_uri=job.replay_uri,
        debug_dir=job.debug_dir,
        seed=job.seed,
        max_action_time_ms=job.max_action_time_ms,
        device=device,
        allow_network=allow_network,
    )
