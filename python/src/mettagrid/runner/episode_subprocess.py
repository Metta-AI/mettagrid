from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.runner.policy_server.websocket_transport import PolicyStepError, WebSocketPolicyServerClient
from mettagrid.runner.rollout import resolve_env_for_seed, single_episode_rollout
from mettagrid.runner.types import PureSingleEpisodeJob, RunnerErrorType
from mettagrid.util.file import write_data

logger = logging.getLogger(__name__)


def _setup_trace_path(debug_dir: Optional[str]) -> Optional[Path]:
    if debug_dir is None:
        return None
    debug_path = Path(debug_dir)
    debug_path.mkdir(parents=True, exist_ok=True)
    return debug_path / "trace.json"


def _classify(exc: Exception) -> RunnerErrorType:
    if isinstance(exc, PolicyStepError):
        return "policy_error"
    if isinstance(exc, ValidationError):
        return "config_error"
    return "unknown"


def _write_error(path: str, exc: Exception) -> None:
    error = {"error_type": _classify(exc), "message": str(exc)[:2000]}
    Path(path).write_text(json.dumps(error))


def _run(job: PureSingleEpisodeJob) -> None:
    env_for_rollout = resolve_env_for_seed(job.env, job.seed)
    env_interface = PolicyEnvInterface.from_mg_cfg(env_for_rollout)
    # TODO: spawn these in parallel since each will need to handle its own prepare step
    policies = [WebSocketPolicyServerClient(env_interface, url=uri) for uri in job.policy_uris]
    trace_path = _setup_trace_path(job.debug_dir)

    try:
        results, replay = single_episode_rollout(
            policies,
            job.assignments,
            env_for_rollout,
            seed=job.seed,
            max_action_time_ms=job.max_action_time_ms,
            overage_budget_ms=job.overage_budget_ms,
            render_mode="none",
            autostart=False,
            capture_replay=job.replay_uri is not None,
            trace_path=trace_path,
        )
    finally:
        for p in policies:
            p.close()

    if job.replay_uri is not None:
        if replay is None:
            raise ValueError("No replay was generated")
        replay.write_replay(job.replay_uri)
    if job.results_uri is not None:
        write_data(job.results_uri, results.model_dump_json(), content_type="application/json")


def main() -> None:
    with open(sys.argv[1]) as f:
        args = json.load(f)
    error_file = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        job = PureSingleEpisodeJob.model_validate(args["job"])
        _run(job)
    except Exception as exc:
        if error_file:
            try:
                _write_error(error_file, exc)
            except Exception:
                logger.warning("Failed to write structured subprocess error", exc_info=True)
        raise


if __name__ == "__main__":
    main()
