import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.policy.prepare_policy_spec import download_policy_spec_from_s3_as_zip
from mettagrid.runner.job_specs import SingleEpisodeJob
from mettagrid.runner.policy_server_manager import PolicyServerHandle, launch_policy_server
from mettagrid.runner.pure_single_episode_runner import PureSingleEpisodeJob, PureSingleEpisodeResult
from mettagrid.util.file import read
from mettagrid.util.uri_resolvers.base import FileParsedScheme, S3ParsedScheme
from mettagrid.util.uri_resolvers.schemes import resolve_uri

logger = logging.getLogger(__name__)


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


def _localize_file_uri(resolved: FileParsedScheme, uri: str) -> str:
    if resolved.local_path is None or not resolved.local_path.exists():
        raise FileNotFoundError(f"Policy path does not exist: {uri}")
    return resolved.local_path.as_uri()


def _localize_s3_uri(resolved: S3ParsedScheme, _uri: str) -> str:
    return download_policy_spec_from_s3_as_zip(
        resolved.canonical,
        remove_downloaded_copy_on_exit=True,
    ).as_uri()


_SCHEME_LOCALIZERS = {
    "mock": lambda resolved, _uri: resolved.canonical,
    "file": _localize_file_uri,
    "s3": _localize_s3_uri,
}


def _localize_policy_uri(uri: str, temp_dirs: list[Path]) -> str:
    if _is_presigned_url(uri):
        return _download_presigned_policy(uri, temp_dirs).as_uri()

    resolved = resolve_uri(uri)
    localizer = _SCHEME_LOCALIZERS.get(resolved.scheme)
    if localizer is None:
        raise ValueError(f"Unsupported policy URI: {uri}")
    return localizer(resolved, uri)


def _spawn_policy_servers(
    local_policy_uris: list[str],
    env_interface: PolicyEnvInterface,
) -> tuple[list[PolicyServerHandle], list[str]]:
    unique_uris = list(dict.fromkeys(local_policy_uris))
    uri_to_server: dict[str, PolicyServerHandle] = {}
    servers: list[PolicyServerHandle] = []
    futures: dict = {}
    try:
        with ThreadPoolExecutor(max_workers=len(unique_uris)) as pool:
            futures = {pool.submit(launch_policy_server, uri, env_interface): uri for uri in unique_uris}
            for future in as_completed(futures):
                uri = futures[future]
                handle = future.result()
                servers.append(handle)
                uri_to_server[uri] = handle
    except Exception:
        for f in futures:
            f.cancel()
        all_handles = set(servers)
        for f in futures:
            if f.done() and not f.cancelled() and f.exception() is None:
                all_handles.add(f.result())
        for h in all_handles:
            try:
                h.shutdown()
            except Exception:
                pass
        raise
    http_uris = [uri_to_server[uri].base_url for uri in local_policy_uris]
    return servers, http_uris


@dataclass
class EpisodeResult:
    result: PureSingleEpisodeResult
    results_path: Path
    replay_path: Path | None
    debug_dir: Path | None


def run_episode(
    job: SingleEpisodeJob,
    *,
    capture_replay: bool = False,
    debug_dir: Path | None = None,
) -> EpisodeResult:
    work_dir = Path(tempfile.mkdtemp())
    servers: list[PolicyServerHandle] = []
    policy_temp_dirs: list[Path] = []
    success = False
    try:
        local_policy_uris = [_localize_policy_uri(uri, policy_temp_dirs) for uri in job.policy_uris]
        env_interface = PolicyEnvInterface.from_mg_cfg(job.env)
        servers, http_policy_uris = _spawn_policy_servers(local_policy_uris, env_interface)

        results_path = work_dir / "results.json"
        replay_path = work_dir / "replay.json.z" if capture_replay else None

        local_results_uri = results_path.as_uri()
        local_replay_uri = replay_path.as_uri() if replay_path else None

        pure_job = PureSingleEpisodeJob(
            policy_uris=http_policy_uris,
            assignments=job.assignments,
            env=job.env,
            results_uri=local_results_uri,
            replay_uri=local_replay_uri,
            debug_dir=str(debug_dir) if debug_dir else None,
            seed=job.seed,
            max_action_time_ms=job.max_action_time_ms,
        )

        with tempfile.NamedTemporaryFile(delete=True) as job_spec_tmp_file:
            pure_job_spec = {
                "job": pure_job.model_dump(),
                "device": "cpu",
            }
            job_spec_tmp_file.write(json.dumps(pure_job_spec).encode("utf-8"))
            job_spec_tmp_file.flush()

            env = {**os.environ, "PYTHONPERFSUPPORT": "1"} if debug_dir else None
            proc = subprocess.Popen(
                [sys.executable, "-m", "mettagrid.runner.pure_single_episode_runner", job_spec_tmp_file.name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )

            stdout, stderr = proc.communicate()

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
                raise RuntimeError(f"pure_single_episode_runner failed ({detail})")

        result = PureSingleEpisodeResult.model_validate_json(read(local_results_uri))
        success = True

        return EpisodeResult(
            result=result,
            results_path=results_path,
            replay_path=replay_path,
            debug_dir=debug_dir,
        )

    finally:
        for server in servers:
            try:
                server.shutdown()
            except Exception:
                pass
        for temp_dir in policy_temp_dirs:
            shutil.rmtree(temp_dir, ignore_errors=True)
        if not success:
            shutil.rmtree(work_dir, ignore_errors=True)
            if debug_dir:
                shutil.rmtree(debug_dir, ignore_errors=True)
