import logging
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from mettagrid.policy.policy_env_interface import PolicyEnvInterface

logger = logging.getLogger(__name__)

_HEALTH_POLL_INTERVAL = 0.1


@dataclass
class PolicyServerHandle:
    port: int
    process: subprocess.Popen
    policy_uri: str
    _stderr_path: Path | None = None
    _env_interface_path: Path | None = None
    _port_file_path: Path | None = None

    def shutdown(self) -> None:
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        for path in (self._stderr_path, self._env_interface_path, self._port_file_path):
            if path is not None:
                path.unlink(missing_ok=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


def launch_policy_server(
    policy_uri: str,
    env_interface: PolicyEnvInterface,
    *,
    startup_timeout: float = 30.0,
) -> PolicyServerHandle:
    env_interface_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    env_interface_file.write(env_interface.model_dump_json())
    env_interface_file.close()

    port_file_fd = tempfile.NamedTemporaryFile(suffix=".port", delete=False)
    port_file_fd.close()
    port_file_path = Path(port_file_fd.name)
    port_file_path.unlink()

    stderr_file = tempfile.NamedTemporaryFile(mode="w", suffix=".stderr", delete=False)
    stderr_path = Path(stderr_file.name)

    cmd = [
        sys.executable,
        "-m",
        "mettagrid.runner.serve_policy",
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
        stdout=subprocess.DEVNULL,
        stderr=stderr_file,
    )
    stderr_file.close()

    deadline = time.monotonic() + startup_timeout
    port = _wait_for_port_file(port_file_path, process, stderr_path, deadline)
    _wait_for_health(port, process, stderr_path, deadline)

    env_interface_path = Path(env_interface_file.name)
    logger.info("Policy server for %s ready on port %d (pid %d)", policy_uri, port, process.pid)
    return PolicyServerHandle(
        port=port,
        process=process,
        policy_uri=policy_uri,
        _stderr_path=stderr_path,
        _env_interface_path=env_interface_path,
        _port_file_path=port_file_path,
    )


def _read_stderr(stderr_path: Path) -> str:
    try:
        return stderr_path.read_text()
    except OSError:
        return ""


def _wait_for_port_file(port_file: Path, process: subprocess.Popen, stderr_path: Path, deadline: float) -> int:
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stderr = _read_stderr(stderr_path)
            raise RuntimeError(
                f"Policy server exited with code {process.returncode} before writing port file.\nstderr: {stderr}"
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


def _wait_for_health(port: int, process: subprocess.Popen, stderr_path: Path, deadline: float) -> None:
    url = f"http://127.0.0.1:{port}/health"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stderr = _read_stderr(stderr_path)
            raise RuntimeError(
                f"Policy server exited with code {process.returncode} before becoming healthy.\nstderr: {stderr}"
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
