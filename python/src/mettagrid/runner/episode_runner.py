import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

from mettagrid.runner.policy_server.manager import LocalPolicyServerHandle, launch_local_policy_server
from mettagrid.runner.types import EpisodeSpec, PureSingleEpisodeJob, PureSingleEpisodeResult
from mettagrid.util.file import read
from mettagrid.util.uri_resolvers.schemes import localize_uri, resolve_uri

logger = logging.getLogger(__name__)


def _to_file_uri(path: Path) -> str:
    return path.resolve().as_uri()


def _is_presigned_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http"):
        return False
    query_params = parse_qs(parsed.query)
    return "X-Amz-Algorithm" in query_params or "AWSAccessKeyId" in query_params


def _download_presigned_policy(url: str, temp_dirs: list[Path]) -> Path:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    temp_dir = Path(tempfile.mkdtemp())
    temp_dirs.append(temp_dir)
    local_path = temp_dir / "policy.zip"
    local_path.write_bytes(response.content)
    return local_path


def _localize_policy_uri(uri: str, temp_dirs: list[Path]) -> str:
    if _is_presigned_url(uri):
        return _download_presigned_policy(uri, temp_dirs).as_uri()
    resolved = resolve_uri(uri)
    if resolved.scheme == "mock":
        return resolved.canonical
    local = localize_uri(uri)
    assert local is not None, f"localize_uri returned None for: {uri}"
    return local.as_uri()


def _spawn_policy_servers(
    local_policy_uris: list[str],
) -> tuple[list[LocalPolicyServerHandle], list[str]]:
    unique_uris = list(dict.fromkeys(local_policy_uris))
    uri_to_server: dict[str, LocalPolicyServerHandle] = {}
    servers: list[LocalPolicyServerHandle] = []
    futures: dict = {}
    try:
        with ThreadPoolExecutor(max_workers=len(unique_uris)) as pool:
            futures = {pool.submit(launch_local_policy_server, uri): uri for uri in unique_uris}
            for future in as_completed(futures):
                uri = futures[future]
                handle = future.result()
                servers.append(handle)
                uri_to_server[uri] = handle
    except Exception:
        for f in futures:
            f.cancel()
        # LocalPolicyServerHandle is not hashable (it contains a Popen), so de-dup by identity.
        all_handles: dict[int, LocalPolicyServerHandle] = {id(h): h for h in servers}
        for f in futures:
            if f.done() and not f.cancelled() and f.exception() is None:
                h = f.result()
                all_handles[id(h)] = h
        for h in all_handles.values():
            try:
                h.shutdown()
            except Exception:
                pass
        raise
    http_uris = [uri_to_server[uri].base_url for uri in local_policy_uris]
    return servers, http_uris


def run_episode_isolated(
    spec: EpisodeSpec,
    results_path: Path,
    *,
    replay_path: Path | None = None,
    debug_dir: Path | None = None,
) -> PureSingleEpisodeResult:
    """Run a single episode in a sandboxed subprocess with process-level isolation.

    Policies are downloaded/localized, served over HTTP via policy servers, and
    the actual simulation runs in a child process (episode_subprocess).
    """
    servers: list[LocalPolicyServerHandle] = []
    policy_temp_dirs: list[Path] = []
    try:
        t0 = time.monotonic()
        local_policy_uris = [_localize_policy_uri(uri, policy_temp_dirs) for uri in spec.policy_uris]
        logger.info(f"Policy localization took {time.monotonic() - t0:.1f}s for {len(spec.policy_uris)} policies")

        t1 = time.monotonic()
        servers, http_policy_uris = _spawn_policy_servers(local_policy_uris)
        logger.info(f"Policy servers spawned in {time.monotonic() - t1:.1f}s")

        local_results_uri = _to_file_uri(results_path)
        local_replay_uri = _to_file_uri(replay_path) if replay_path else None

        pure_job = PureSingleEpisodeJob(
            policy_uris=http_policy_uris,
            assignments=spec.assignments,
            env=spec.env,
            results_uri=local_results_uri,
            replay_uri=local_replay_uri,
            debug_dir=str(debug_dir) if debug_dir else None,
            seed=spec.seed,
            max_action_time_ms=spec.max_action_time_ms,
        )

        with tempfile.NamedTemporaryFile(delete=True) as job_spec_tmp_file:
            pure_job_spec = {
                "job": pure_job.model_dump(),
                "device": "cpu",
            }
            job_spec_tmp_file.write(json.dumps(pure_job_spec).encode("utf-8"))
            job_spec_tmp_file.flush()

            env = {**os.environ, "PYTHONPERFSUPPORT": "1"} if debug_dir else None
            t2 = time.monotonic()
            logger.info("Launching episode subprocess")
            proc = subprocess.Popen(
                [sys.executable, "-m", "mettagrid.runner.episode_subprocess", job_spec_tmp_file.name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )

            stdout, stderr = proc.communicate()
            logger.info(f"Episode subprocess finished in {time.monotonic() - t2:.1f}s (exit code {proc.returncode})")

            if stdout:
                logger.info("Episode runner stdout:\n%s", stdout.rstrip())
            if stderr:
                logger.info("Episode runner stderr:\n%s", stderr.rstrip())

            if proc.returncode != 0:
                for server in servers:
                    logs = server.read_logs()
                    if logs.strip():
                        logger.error(
                            "Policy server %s (pid %d) logs:\n%s",
                            server.policy_uri,
                            server.process.pid,
                            logs.rstrip(),
                        )
                code = proc.returncode
                detail = f"signal {-code}" if code < 0 else f"exit {code}"
                raise RuntimeError(f"episode_subprocess failed ({detail})")

        return PureSingleEpisodeResult.model_validate_json(read(local_results_uri))

    finally:
        for server in servers:
            try:
                server.shutdown()
            except Exception:
                pass
        for temp_dir in policy_temp_dirs:
            shutil.rmtree(temp_dir, ignore_errors=True)
