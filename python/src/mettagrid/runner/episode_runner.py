import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

from mettagrid.policy.loader import discover_and_register_policies
from mettagrid.policy.policy_registry import get_policy_registry
from mettagrid.runner.policy_server.manager import LocalPolicyServerHandle, launch_local_policy_server
from mettagrid.runner.types import EpisodeSpec, PureSingleEpisodeJob, PureSingleEpisodeResult, RunnerError
from mettagrid.util.file import read
from mettagrid.util.module import load_symbol
from mettagrid.util.uri_resolvers.schemes import localize_uri, resolve_uri

logger = logging.getLogger(__name__)

MAX_POLICY_LOG_BYTES = 100 * 1024 * 1024  # 100MB


class EpisodeSubprocessError(RuntimeError):
    """Raised when the episode subprocess exits non-zero."""

    def __init__(self, message: str, runner_error: RunnerError | None = None):
        super().__init__(message)
        self.runner_error = runner_error


MAX_POLICY_SIZE_BYTES = 500 * 1024 * 1024  # 500MB


def _read_log_with_limit(path: Path, max_bytes: int = MAX_POLICY_LOG_BYTES) -> bytes:
    """Read log file, truncating to tail if over max_bytes."""
    if not path.exists():
        return b""
    size = path.stat().st_size
    if size == 0:
        return b""
    if size <= max_bytes:
        return path.read_bytes()
    header = f"[truncated: showing last {max_bytes // (1024 * 1024)}MB of {size // (1024 * 1024)}MB]\n".encode()
    with open(path, "rb") as f:
        f.seek(size - max_bytes + len(header))
        f.readline()  # Skip to next newline for clean truncation
        return header + f.read()


def _to_file_uri(path: Path) -> str:
    return path.resolve().as_uri()


def _is_presigned_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http"):
        return False
    query_params = parse_qs(parsed.query)
    return "X-Amz-Algorithm" in query_params or "AWSAccessKeyId" in query_params


def _download_presigned_policy(url: str, temp_dirs: list[Path]) -> Path:
    response = requests.get(url, timeout=30, stream=True)
    response.raise_for_status()
    temp_dir = Path(tempfile.mkdtemp())
    temp_dirs.append(temp_dir)
    local_path = temp_dir / "policy.zip"
    downloaded = 0
    with open(local_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            downloaded += len(chunk)
            if downloaded > MAX_POLICY_SIZE_BYTES:
                raise ValueError(f"Policy exceeds {MAX_POLICY_SIZE_BYTES // (1024 * 1024)} MB limit")
            f.write(chunk)
    return local_path


def _is_builtin_or_classpath_metta_policy_uri(uri: str) -> bool:
    parsed = urlparse(uri)
    if parsed.scheme != "metta" or parsed.netloc != "policy":
        return False

    identifier = parsed.path.lstrip("/")
    if not identifier:
        return False

    # Preserve explicit class paths (metta://policy/package.module.Class) so policy
    # loading semantics match local execution.
    if "." in identifier and ":v" not in identifier and not identifier.endswith(":latest"):
        if load_symbol(identifier, strict=False) is not None:
            return True

    discover_and_register_policies()
    return identifier in get_policy_registry()


def _localize_policy_uri(uri: str, temp_dirs: list[Path]) -> str:
    if _is_builtin_or_classpath_metta_policy_uri(uri):
        return uri
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
    per_policy_envs: dict[int, dict[str, str]] | None = None,
) -> tuple[list[LocalPolicyServerHandle], list[str]]:
    if not local_policy_uris:
        return [], []

    servers: list[LocalPolicyServerHandle] = []
    futures: list = []
    try:
        with ThreadPoolExecutor(max_workers=len(local_policy_uris)) as pool:
            futures = [
                pool.submit(
                    launch_local_policy_server,
                    uri,
                    extra_env=(per_policy_envs or {}).get(i) or None,
                )
                for i, uri in enumerate(local_policy_uris)
            ]
            # Read results in submission order so returned URIs line up with local_policy_uris.
            servers = [future.result() for future in futures]
    except Exception:
        for future in futures:
            future.cancel()
        # LocalPolicyServerHandle is not hashable (it contains a Popen), so de-dup by identity.
        all_handles: dict[int, LocalPolicyServerHandle] = {id(h): h for h in servers}
        for future in futures:
            if future.done() and not future.cancelled() and future.exception() is None:
                handle = future.result()
                all_handles[id(handle)] = handle
        for h in all_handles.values():
            try:
                h.shutdown()
            except Exception:
                pass
        raise
    http_uris = [server.base_url for server in servers]
    return servers, http_uris


def _per_agent_policy_mapping(
    local_policy_uris: list[str],
    assignments: list[int],
    num_agents: int,
) -> tuple[list[str], list[int], dict[int, int]]:
    if len(assignments) != num_agents or not all(
        0 <= assignment < len(local_policy_uris) for assignment in assignments
    ):
        raise ValueError("Assignments must match agent count and be within policy range")

    # Launch one policy server per referenced policy index, not per agent.
    # This preserves assignment semantics while avoiding N-agent process blowups.
    policy_index_remap: dict[int, int] = {}
    compact_policy_uris: list[str] = []
    compact_assignments: list[int] = []
    for assignment in assignments:
        remapped_index = policy_index_remap.get(assignment)
        if remapped_index is None:
            remapped_index = len(compact_policy_uris)
            policy_index_remap[assignment] = remapped_index
            compact_policy_uris.append(local_policy_uris[assignment])
        compact_assignments.append(remapped_index)
    return compact_policy_uris, compact_assignments, policy_index_remap


def _read_subprocess_error(error_file: Path) -> RunnerError | None:
    """Read the error file written by the subprocess, if it exists."""
    if not error_file.exists():
        return None
    try:
        return RunnerError.model_validate_json(error_file.read_text())
    except Exception:
        logger.warning("Failed to parse subprocess error file %s", error_file, exc_info=True)
        return None


def run_episode_isolated(
    spec: EpisodeSpec,
    results_path: Path,
    *,
    replay_path: Path | None = None,
    debug_dir: Path | None = None,
    policy_log_dir: Path | None = None,
    policy_secrets: dict[int, dict[str, str]] | None = None,
) -> PureSingleEpisodeResult:
    """Run a single episode in a sandboxed subprocess with process-level isolation.

    Policies are downloaded/localized, served over HTTP via policy servers, and
    the actual simulation runs in a child process (episode_subprocess).

    Args:
        spec: Episode specification including policy URIs and assignments.
        results_path: Path to write episode results.
        replay_path: Optional path to write replay data.
        debug_dir: Optional directory for debug output.
        policy_log_dir: Optional directory for per-agent policy server logs.
            If provided, logs are copied as {agent_idx}.log after the episode completes.
        policy_secrets: Per-policy environment variables keyed by policy index
            (matches position in spec.policy_uris). Each policy subprocess will only
            receive its own secrets.
    """
    servers: list[LocalPolicyServerHandle] = []
    policy_temp_dirs: list[Path] = []
    try:
        t0 = time.monotonic()
        local_policy_uris = [_localize_policy_uri(uri, policy_temp_dirs) for uri in spec.policy_uris]
        logger.info(f"Policy localization took {time.monotonic() - t0:.1f}s for {len(spec.policy_uris)} policies")

        t1 = time.monotonic()
        per_agent_policy_uris, per_agent_assignments, policy_index_remap = _per_agent_policy_mapping(
            local_policy_uris,
            spec.assignments,
            spec.env.game.num_agents,
        )

        # Remap policy_secrets from original indices to compact indices
        compact_secrets: dict[int, dict[str, str]] | None = None
        if policy_secrets:
            compact_secrets = {
                compact_idx: policy_secrets[orig_idx]
                for orig_idx, compact_idx in policy_index_remap.items()
                if orig_idx in policy_secrets
            }

        servers, http_policy_uris = _spawn_policy_servers(per_agent_policy_uris, compact_secrets)
        logger.info(
            "Policy servers spawned in %.1fs for %d compact policies (%d agents)",
            time.monotonic() - t1,
            len(http_policy_uris),
            len(spec.assignments),
        )

        local_results_uri = _to_file_uri(results_path)
        local_replay_uri = _to_file_uri(replay_path) if replay_path else None

        pure_job = PureSingleEpisodeJob(
            policy_uris=http_policy_uris,
            assignments=per_agent_assignments,
            env=spec.env,
            results_uri=local_results_uri,
            replay_uri=local_replay_uri,
            debug_dir=str(debug_dir) if debug_dir else None,
            seed=spec.seed,
            max_action_time_ms=spec.max_action_time_ms,
            overage_budget_ms=spec.overage_budget_ms,
        )

        with (
            tempfile.NamedTemporaryFile(delete=True) as job_spec_tmp_file,
            tempfile.NamedTemporaryFile(delete=True, suffix=".json") as error_tmp_file,
        ):
            pure_job_spec = {
                "job": pure_job.model_dump(),
                "device": "cpu",
            }
            job_spec_tmp_file.write(json.dumps(pure_job_spec).encode("utf-8"))
            job_spec_tmp_file.flush()

            error_file_path = Path(error_tmp_file.name)

            env = {**os.environ, "PYTHONPERFSUPPORT": "1"} if debug_dir else None
            t2 = time.monotonic()
            logger.info("Launching episode subprocess")
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "mettagrid.runner.episode_subprocess",
                    job_spec_tmp_file.name,
                    error_tmp_file.name,
                ],
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
                runner_error = _read_subprocess_error(error_file_path)
                raise EpisodeSubprocessError(f"episode_subprocess failed ({detail})", runner_error=runner_error)

        # Copy policy logs to output directory if requested.
        # We keep one log artifact per agent index for compatibility with
        # downstream upload consumers, even when multiple agents share a
        # compacted policy server.
        if policy_log_dir is not None:
            policy_log_dir.mkdir(parents=True, exist_ok=True)
            for agent_idx, policy_idx in enumerate(per_agent_assignments):
                shutil.copy(servers[policy_idx]._log_file, policy_log_dir / f"{agent_idx}.log")

        return PureSingleEpisodeResult.model_validate_json(read(local_results_uri))

    finally:
        for server in servers:
            try:
                server.shutdown()
            except Exception:
                pass
        for temp_dir in policy_temp_dirs:
            shutil.rmtree(temp_dir, ignore_errors=True)
