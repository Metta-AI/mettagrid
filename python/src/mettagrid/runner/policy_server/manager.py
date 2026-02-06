import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_HEALTH_POLL_INTERVAL = 0.1


def _get_mettagrid_source() -> tuple[str, str]:
    """Return (pip install spec, requires_python) from the currently installed mettagrid."""
    try:
        dist = distribution("mettagrid")
    except PackageNotFoundError:
        return _get_pypi_latest("mettagrid")

    requires_python = dist.metadata["Requires-Python"]

    direct_url_text = dist.read_text("direct_url.json")
    if direct_url_text:
        url = json.loads(direct_url_text).get("url", "")
        if url.startswith("file://"):
            return url.removeprefix("file://"), requires_python

    return f"mettagrid=={dist.metadata['Version']}", requires_python


def _get_pypi_latest(package: str) -> tuple[str, str]:
    response = requests.get(f"https://pypi.org/pypi/{package}/json", timeout=10)
    response.raise_for_status()
    info = response.json()["info"]
    return f"{package}=={info['version']}", info["requires_python"]


def _create_policy_venv(mettagrid_source: str, requires_python: str) -> Path:
    policy_dir = Path(tempfile.mkdtemp(prefix="policy-"))
    venv_path = policy_dir / ".venv"
    venv_python = venv_path / "bin" / "python"
    subprocess.run(["uv", "venv", str(venv_path), "--python", requires_python], check=True)
    subprocess.run(
        ["uv", "pip", "install", "--python", str(venv_python), mettagrid_source, "torch"],
        check=True,
    )
    return policy_dir


@dataclass(kw_only=True)
class LocalPolicyServerHandle:
    port: int
    process: subprocess.Popen
    policy_uri: str
    _log_file: Path = field(repr=False)
    _ready_file_path: Path | None = None
    _venv_dir: Path | None = None

    def shutdown(self) -> None:
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        for path in (self._log_file, self._ready_file_path):
            if path is not None:
                path.unlink(missing_ok=True)
        if self._venv_dir is not None:
            shutil.rmtree(self._venv_dir, ignore_errors=True)

    def read_logs(self, max_bytes: int = 8192) -> str:
        return _read_log_tail(self._log_file, max_bytes)

    @property
    def base_url(self) -> str:
        return f"ws://127.0.0.1:{self.port}"


def launch_local_policy_server(
    policy_uri: str,
    *,
    startup_timeout: float = 30.0,
) -> LocalPolicyServerHandle:
    """Launch a local policy server subprocess using WebSocket."""
    ready_file_fd = tempfile.NamedTemporaryFile(suffix=".ready", delete=False)
    ready_file_fd.close()
    ready_file_path = Path(ready_file_fd.name)
    ready_file_path.unlink()

    log_file = tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False)

    if os.environ.get("EPISODE_RUNNER_USE_ISOLATED_VENVS") != "0":
        mettagrid_source, requires_python = _get_mettagrid_source()
        venv_dir = _create_policy_venv(mettagrid_source, requires_python)
        python = str(venv_dir / ".venv" / "bin" / "python")
    else:
        python = sys.executable
        venv_dir = None

    cmd = [
        python,
        "-m",
        "mettagrid.runner.policy_server.server",
        "--policy",
        policy_uri,
        "--host",
        "127.0.0.1",
        "--port",
        "0",
        "--ready-file",
        str(ready_file_path),
    ]

    process = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=log_file,
    )
    log_file.close()
    log_path = Path(log_file.name)

    deadline = time.monotonic() + startup_timeout
    _wait_for_ready_file(ready_file_path, process, log_path, deadline)

    port = int(ready_file_path.read_text().strip())
    logger.info("Policy server for %s ready on ws://127.0.0.1:%d (pid %d)", policy_uri, port, process.pid)
    return LocalPolicyServerHandle(
        port=port,
        process=process,
        policy_uri=policy_uri,
        _log_file=log_path,
        _ready_file_path=ready_file_path,
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


def _wait_for_ready_file(ready_file: Path, process: subprocess.Popen, log_path: Path, deadline: float) -> None:
    while time.monotonic() < deadline:
        if process.poll() is not None:
            log_tail = _read_log_tail(log_path)
            raise RuntimeError(
                f"Policy server exited with code {process.returncode} before becoming ready.\noutput:\n{log_tail}"
            )
        if ready_file.exists() and ready_file.read_text().strip():
            return
        time.sleep(_HEALTH_POLL_INTERVAL)
    process.kill()
    process.wait()
    raise TimeoutError("Policy server did not become ready in time")
