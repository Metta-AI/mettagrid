import io
import json
import logging
import os
import shutil
import signal
import sys
import tempfile
import time
import zipfile
from contextlib import nullcontext
from pathlib import Path

from mettagrid.base_config import LENIENT_CONTEXT
from mettagrid.runner.episode_runner import (
    EpisodeSubprocessError,
    _read_log_with_limit,
    run_episode_isolated,
)
from mettagrid.runner.types import RunnerError, RunnerErrorType, RuntimeInfo, SingleEpisodeJob
from mettagrid.util.file import copy_data, read, write_data
from mettagrid.util.tracer import Tracer

logger = logging.getLogger(__name__)


def _write_runner_error(
    error_info_uri: str | None,
    error_type: RunnerErrorType,
    message: str,
) -> None:
    """Write a structured error artifact to S3 so the event processor can read it directly.

    Best-effort: never masks the original exception if S3 write fails.
    """
    if not error_info_uri:
        return
    try:
        error = RunnerError(error_type=error_type, message=message[:2000])
        write_data(error_info_uri, error.model_dump_json().encode("utf-8"), content_type="application/json")
        logger.info(f"Wrote runner error: type={error_type}")
    except Exception as e:
        logger.warning(f"Failed to write runner error: {e}")


def _upload_debug_dir(local_debug_dir: str | None, debug_uri: str | None) -> None:
    if local_debug_dir is None or debug_uri is None:
        return
    if not os.path.isdir(local_debug_dir):
        return
    try:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for abs_dir, _, filenames in os.walk(local_debug_dir):
                for filename in filenames:
                    abs_file = os.path.join(abs_dir, filename)
                    arcname = os.path.relpath(abs_file, local_debug_dir)
                    zf.write(abs_file, arcname)
        write_data(debug_uri, buf.getvalue(), content_type="application/zip")
        logger.info(f"Uploaded debug.zip to {debug_uri}")
    except Exception as e:
        logger.warning(f"Failed to upload debug.zip: {e}")


def _upload_policy_logs(
    policy_log_dir: Path | None,
    policy_log_urls: dict[str, str] | None,
) -> None:
    """Upload policy logs to configured URIs.

    Args:
        policy_log_dir: Directory containing policy log files named like "{agent_idx}.log"
        policy_log_urls: Dict mapping "{agent_idx}" to destination URIs
    """
    if policy_log_dir is None or policy_log_urls is None:
        return
    if not policy_log_dir.is_dir():
        return
    for log_file in policy_log_dir.iterdir():
        if not log_file.is_file():
            continue
        # Extract key from filename: "0_stdout.log" -> "0_stdout"
        key = log_file.stem
        presigned_url = policy_log_urls.get(key)
        if presigned_url is None:
            logger.warning(f"No presigned URL for policy log {log_file.name}, skipping")
            continue
        try:
            content = _read_log_with_limit(log_file)
            write_data(presigned_url, content, content_type="text/plain")
            logger.info(f"Uploaded policy log {log_file.name} ({len(content)} bytes)")
        except Exception as e:
            logger.warning(f"Failed to upload policy log {log_file.name}: {e}")


def _upload_results(
    results_path: Path,
    replay_path: Path | None,
    results_uri: str | None,
    replay_uri: str | None,
    debug_dir: Path | None,
    debug_uri: str | None,
    policy_log_dir: Path | None = None,
    policy_log_urls: dict[str, str] | None = None,
) -> None:
    if results_uri and results_path.exists():
        copy_data(results_path.as_uri(), results_uri, content_type="application/json")
        logger.info(f"Uploaded results to {results_uri}")

    if replay_uri and replay_path is not None and replay_path.exists():
        copy_data(replay_path.as_uri(), replay_uri, content_type="application/x-compress")
        logger.info(f"Uploaded replay to {replay_uri}")

    _upload_debug_dir(str(debug_dir) if debug_dir else None, debug_uri)
    _upload_policy_logs(policy_log_dir, policy_log_urls)


def _collect_runtime_info(git_commit: str | None, cogames_version: str | None) -> RuntimeInfo:
    return RuntimeInfo(git_commit=git_commit, cogames_version=cogames_version)


def _init_logging() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "DEBUG").upper(),
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )


def main() -> None:
    _init_logging()

    job_spec_uri = os.environ.get("JOB_SPEC_URI")
    results_uri = os.environ.get("RESULTS_URI")
    replay_uri = os.environ.get("REPLAY_URI")
    runtime_info_uri = os.environ.get("RUNTIME_INFO_URI")
    git_commit = os.environ.get("GIT_COMMIT")
    cogames_version = os.environ.get("COGAMES_VERSION")

    if not job_spec_uri:
        print("Set JOB_SPEC_URI, RESULTS_URI, REPLAY_URI env vars")
        sys.exit(1)

    error_info_uri = os.environ.get("ERROR_INFO_URI")

    t0 = time.monotonic()
    logger.info(f"Running with spec={job_spec_uri[:80]}")

    if runtime_info_uri:
        runtime_info = _collect_runtime_info(git_commit, cogames_version)
        try:
            payload = runtime_info.model_dump_json(exclude_none=True)
            write_data(runtime_info_uri, payload.encode("utf-8"), content_type="application/json")
            logger.info(f"Uploaded runtime info: {payload}")
        except Exception as e:
            logger.warning(f"Failed to upload runtime info: {e}")

    # Phase 1: Fetch + validate job spec (separate so fetch errors aren't misclassified)
    raw_spec = read(job_spec_uri)
    try:
        job = SingleEpisodeJob.model_validate_json(raw_spec, context=LENIENT_CONTEXT)
    except Exception as e:
        _write_runner_error(error_info_uri, "config_error", str(e))
        raise
    logger.info(f"Job spec loaded in {time.monotonic() - t0:.1f}s")

    debug_uri = os.environ.get("DEBUG_URI")
    policy_log_urls_json = os.environ.get("POLICY_LOG_URLS")
    policy_log_urls: dict[str, str] | None = json.loads(policy_log_urls_json) if policy_log_urls_json else None
    capture_replay = replay_uri is not None

    with tempfile.TemporaryDirectory() as output_dir_str:
        output_dir = Path(output_dir_str)
        debug_dir = Path(tempfile.mkdtemp()) if debug_uri else None
        policy_log_dir = Path(tempfile.mkdtemp(prefix="policy-logs-")) if policy_log_urls else None

        tracer: Tracer | None = None
        if debug_dir:
            tracer = Tracer(debug_dir / "setup_trace.json")
            tracer._write_process_name(Tracer.PID_EXECUTOR, "Executor", sort_index=-2)

        pid = Tracer.PID_EXECUTOR

        results_path = output_dir / "results.json"
        replay_path = output_dir / "replay.json.z" if capture_replay else None

        def sigterm_handler(_signum: int, _frame: object) -> None:
            logger.warning("Received SIGTERM, uploading debug_dir before exit...")
            if tracer:
                tracer.flush()
            _upload_debug_dir(str(debug_dir) if debug_dir else None, debug_uri)
            sys.exit(128 + signal.SIGTERM)

        if debug_dir:
            try:
                signal.signal(signal.SIGTERM, sigterm_handler)
            except ValueError:
                pass  # Not in main thread of the main interpreter

        try:
            t_episode = time.monotonic()
            logger.info("Starting episode run")
            with tracer.span("run_episode", pid=pid) if tracer else nullcontext():
                run_episode_isolated(
                    job.episode_spec(),
                    results_path,
                    replay_path=replay_path,
                    debug_dir=debug_dir,
                    policy_log_dir=policy_log_dir,
                )
            logger.info(f"Episode run completed in {time.monotonic() - t_episode:.1f}s")

            if tracer:
                tracer.flush()

            t_upload = time.monotonic()
            _upload_results(
                results_path,
                replay_path,
                results_uri,
                replay_uri,
                debug_dir,
                debug_uri,
                policy_log_dir,
                policy_log_urls,
            )
            logger.info(f"Upload completed in {time.monotonic() - t_upload:.1f}s")

            logger.info(f"Job completed successfully, total time {time.monotonic() - t0:.1f}s")
        except EpisodeSubprocessError as e:
            if e.runner_error:
                _write_runner_error(
                    error_info_uri,
                    e.runner_error.error_type,
                    e.runner_error.message,
                )
            else:
                _write_runner_error(error_info_uri, "unknown", str(e))
            raise
        except Exception as e:
            # Pre-subprocess: only policy localization/spawn can fail here
            _write_runner_error(error_info_uri, "policy_error", str(e))
            raise
        finally:
            if tracer:
                tracer.flush()
            if debug_dir:
                shutil.rmtree(debug_dir, ignore_errors=True)
            if policy_log_dir:
                shutil.rmtree(policy_log_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
