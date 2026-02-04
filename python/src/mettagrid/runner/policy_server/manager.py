import logging
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests

from mettagrid.policy.policy_env_interface import PolicyEnvInterface

logger = logging.getLogger(__name__)

_HEALTH_POLL_INTERVAL = 0.1


@dataclass(kw_only=True)
class LocalPolicyServerHandle:
    port: int
    process: subprocess.Popen
    policy_uri: str
    _log_file: Path = field(repr=False)
    _env_interface_path: Path | None = None
    _port_file_path: Path | None = None

    def shutdown(self) -> None:
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        for path in (self._log_file, self._env_interface_path, self._port_file_path):
            if path is not None:
                path.unlink(missing_ok=True)

    def read_logs(self, max_bytes: int = 8192) -> str:
        return _read_log_tail(self._log_file, max_bytes)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


def launch_local_policy_server(
    policy_uri: str,
    env_interface: PolicyEnvInterface,
    *,
    startup_timeout: float = 30.0,
) -> LocalPolicyServerHandle:
    env_interface_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    env_interface_file.write(env_interface.model_dump_json())
    env_interface_file.close()

    port_file_fd = tempfile.NamedTemporaryFile(suffix=".port", delete=False)
    port_file_fd.close()
    port_file_path = Path(port_file_fd.name)
    port_file_path.unlink()

    log_file = tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False)

    cmd = [
        sys.executable,
        "-m",
        "mettagrid.runner.policy_server.server",
        "--policy",
        policy_uri,
        "--env-interface-file",
        env_interface_file.name,
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

    env_interface_path = Path(env_interface_file.name)
    logger.info("Policy server for %s ready on port %d (pid %d)", policy_uri, port, process.pid)
    return LocalPolicyServerHandle(
        port=port,
        process=process,
        policy_uri=policy_uri,
        _log_file=log_path,
        _env_interface_path=env_interface_path,
        _port_file_path=port_file_path,
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
