import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_HEALTH_POLL_INTERVAL = 0.1


def _get_latest_pypi_info(package: str) -> tuple[str, str]:
    try:
        response = requests.get(f"https://pypi.org/pypi/{package}/json", timeout=10)
        response.raise_for_status()
        info = response.json()["info"]
        return info["version"], info["requires_python"]
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to fetch latest {package} version from PyPI: {e}") from e


def _create_policy_venv(mettagrid_version: str, requires_python: str) -> Path:
    policy_dir = Path(tempfile.mkdtemp(prefix="policy-"))
    venv_path = policy_dir / ".venv"
    venv_python = venv_path / "bin" / "python"
    subprocess.run(["uv", "venv", str(venv_path), "--python", requires_python], check=True)
    subprocess.run(
        ["uv", "pip", "install", "--python", str(venv_python), f"mettagrid=={mettagrid_version}", "torch"],
        check=True,
    )
    return policy_dir


@dataclass(kw_only=True)
class LocalPolicyServerHandle:
    port: int
    process: subprocess.Popen
    policy_uri: str
    _log_file: Path = field(repr=False)
    _port_file_path: Path | None = None
    _venv_dir: Path | None = None

    def shutdown(self) -> None:
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        for path in (self._log_file, self._port_file_path):
            if path is not None:
                path.unlink(missing_ok=True)
        if self._venv_dir is not None:
            shutil.rmtree(self._venv_dir, ignore_errors=True)

    def read_logs(self, max_bytes: int = 8192) -> str:
        return _read_log_tail(self._log_file, max_bytes)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


def launch_local_policy_server(
    policy_uri: str,
    *,
    startup_timeout: float = 30.0,
) -> LocalPolicyServerHandle:
    """Launch a local policy server subprocess."""
    port_file_fd = tempfile.NamedTemporaryFile(suffix=".port", delete=False)
    port_file_fd.close()
    port_file_path = Path(port_file_fd.name)
    port_file_path.unlink()

    log_file = tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False)

    # TODO: remove this once we've migrated all policies to use isolated venvs
    if os.environ.get("EPISODE_RUNNER_USE_ISOLATED_VENVS") != "0":
        version, requires_python = _get_latest_pypi_info("mettagrid")
        venv_dir = _create_policy_venv(version, requires_python)
        python = str(venv_dir / ".venv" / "bin" / "python")
    else:
        python = sys.executable

    cmd = [
        python,
        "-m",
        "mettagrid.runner.policy_server.server",
        "--policy",
        policy_uri,
        "--port",
        "0",
        "--port-file",
        str(port_file_path),
    ]

    process = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=log_file,
    )
    log_file.close()
    log_path = Path(log_file.name)

    deadline = time.monotonic() + startup_timeout
    port = _wait_for_port_file(port_file_path, process, log_path, deadline)
    _wait_for_health(port, process, log_path, deadline)

    logger.info("Policy server for %s ready on port %d (pid %d)", policy_uri, port, process.pid)
    return LocalPolicyServerHandle(
        port=port,
        process=process,
        policy_uri=policy_uri,
        _log_file=log_path,
        _port_file_path=port_file_path,
        _venv_dir=venv_dir,
    )


def _read_log_tail(log_path: Path, max_bytes: int = 8192) -> str:
    try:
        size = log_path.stat().st_size
        with open(log_path) as f:
            if size > max_bytes:
                f.seek(size - max_bytes)
                f.readline()
            content = f.read()
            return content if content else f"<log file {size} bytes, no trailing content>"
    except OSError:
        return "<log file not available>"


def _wait_for_port_file(port_file: Path, process: subprocess.Popen, log_path: Path, deadline: float) -> int:
    while time.monotonic() < deadline:
        if process.poll() is not None:
            log_tail = _read_log_tail(log_path)
            raise RuntimeError(
                f"Policy server exited with code {process.returncode} before writing port file.\noutput:\n{log_tail}"
            )
        if port_file.exists():
            try:
                return int(port_file.read_text().strip())
            except ValueError:
                pass
        time.sleep(_HEALTH_POLL_INTERVAL)
    process.kill()
    process.wait()
    raise TimeoutError("Policy server did not write port file in time")


def _wait_for_health(port: int, process: subprocess.Popen, log_path: Path, deadline: float) -> None:
    url = f"http://127.0.0.1:{port}/health"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            log_tail = _read_log_tail(log_path)
            raise RuntimeError(
                f"Policy server exited with code {process.returncode} before becoming healthy.\noutput:\n{log_tail}"
            )
        try:
            resp = requests.get(url, timeout=1)
            if resp.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(_HEALTH_POLL_INTERVAL)
    process.kill()
    process.wait()
    raise TimeoutError(f"Policy server health check at {url} did not pass in time")
