from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.runner.policy_server.websocket_transport import PolicyStepError, WebSocketPolicyServerClient
from mettagrid.runner.rollout import single_episode_rollout
from mettagrid.runner.types import PureSingleEpisodeJob
from mettagrid.util.file import write_data

logger = logging.getLogger(__name__)


def _setup_trace_path(debug_dir: Optional[str]) -> Optional[Path]:
    if debug_dir is None:
        return None
    debug_path = Path(debug_dir)
    debug_path.mkdir(parents=True, exist_ok=True)
    return debug_path / "trace.json"


def main() -> None:
    with open(sys.argv[1]) as f:
        args = json.load(f)
    job = PureSingleEpisodeJob.model_validate(args["job"])

    env_interface = PolicyEnvInterface.from_mg_cfg(job.env)
    # TODO: spawn these in parallel since each will need to handle its own prepare step
    policies = [WebSocketPolicyServerClient(env_interface, url=uri) for uri in job.policy_uris]
    trace_path = _setup_trace_path(job.debug_dir)

    try:
        results, replay = single_episode_rollout(
            policies,
            job.assignments,
            job.env,
            seed=job.seed,
            max_action_time_ms=job.max_action_time_ms,
            render_mode="none",
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

    if job.replay_uri is not None:
        if replay is None:
            raise ValueError("No replay was generated")
        replay.write_replay(job.replay_uri)
    if job.results_uri is not None:
        write_data(job.results_uri, results.model_dump_json(), content_type="application/json")


if __name__ == "__main__":
    main()
