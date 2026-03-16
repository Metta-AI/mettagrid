import importlib
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from importlib.metadata import version as pkg_version
from pathlib import Path

import mettagrid

logger = logging.getLogger(__name__)

_HEALTH_POLL_INTERVAL = 0.1


def _find_package_root(pkg_path: Path) -> Path | None:
    """Walk up from a package directory to find the installable root (has pyproject.toml)."""
    candidate = pkg_path.parent
    while candidate != candidate.parent:
        if (candidate / "pyproject.toml").exists():
            return candidate.resolve()
        candidate = candidate.parent
    return None


def _get_mettagrid_source() -> str:
    """Return a pip-installable spec for the currently running mettagrid."""
    pkg_root = _find_package_root(Path(mettagrid.__path__[0]))
    if pkg_root is not None:
        return str(pkg_root)
    return f"mettagrid=={pkg_version('mettagrid')}"


def _get_package_source(module_name: str, package_name: str) -> str | None:
    """Return a pip-installable spec for an optional dependency package."""
    try:
        module = importlib.import_module(module_name)
    except Exception:
        try:
            return f"{package_name}=={pkg_version(package_name)}"
        except Exception:
            return None

    module_paths = getattr(module, "__path__", ())
    first_path = next(iter(module_paths), None)
    if first_path is not None:
        pkg_root = _find_package_root(Path(first_path))
        if pkg_root is not None:
            return str(pkg_root)

    try:
        return f"{package_name}=={pkg_version(package_name)}"
    except Exception:
        return None


_POLICY_REQUIREMENTS = Path("/opt/policy-requirements.txt")
_POLICY_OVERRIDES = Path("/opt/policy-overrides.txt")
_POLICY_WHEELS = Path("/opt/wheels")


def _create_policy_venv() -> Path:
    policy_dir = Path(tempfile.mkdtemp(prefix="policy-"))
    venv_path = policy_dir / ".venv"
    venv_python = venv_path / "bin" / "python"
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    subprocess.run(["uv", "venv", str(venv_path), "--python", python_version], check=True)
    if _POLICY_REQUIREMENTS.is_file():
        logger.info("Creating policy server venv with requirements from %s", _POLICY_REQUIREMENTS)
        cmd = ["uv", "pip", "install", "--python", str(venv_python), "-r", str(_POLICY_REQUIREMENTS)]
        if _POLICY_WHEELS.is_dir():
            cmd.extend(["--find-links", str(_POLICY_WHEELS)])
        if _POLICY_OVERRIDES.is_file():
            cmd.extend(["--override", str(_POLICY_OVERRIDES)])
        subprocess.run(cmd, check=True)
    else:
        install_targets = [_get_mettagrid_source()]
        for module_name, package_name in (("metta", "metta"), ("cogames_agents", "cogames-agents")):
            package_source = _get_package_source(module_name, package_name)
            if package_source is not None:
                install_targets.append(package_source)
        logger.info("Creating policy server venv with core sources %s", install_targets)
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(venv_python),
                *install_targets,
                "safetensors",
                "packaging",
                "tensordict",
                "torchrl",
                "einops",
            ],
            check=True,
        )
    return policy_dir


@dataclass(kw_only=True, frozen=True)
class LocalPolicyServerHandle:
    port: int
    process: subprocess.Popen
    policy_uri: str
    _log_file: Path = field(repr=False)
    _ready_file_path: Path | None = None
    _venv_dir: Path | None = None

    def __hash__(self) -> int:
        return hash((self.port, self.policy_uri))

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
    startup_timeout: float = 300.0,
    extra_env: dict[str, str] | None = None,
) -> LocalPolicyServerHandle:
    """Launch a local policy server subprocess using WebSocket."""
    with tempfile.NamedTemporaryFile(suffix=".ready", delete=False) as ready_file_fd:
        ready_file_path = Path(ready_file_fd.name)
    ready_file_path.unlink()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as log_file:
        log_path = Path(log_file.name)

        if os.environ.get("EPISODE_RUNNER_USE_ISOLATED_VENVS") != "0":
            venv_dir = _create_policy_venv()
            logger.info("Policy server venv created at %s for policy %s", venv_dir, policy_uri)
            python = str(venv_dir / ".venv" / "bin" / "python")
        else:
            logger.info("Using system Python for policy server for policy %s", policy_uri)
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

        child_env = {**os.environ, **(extra_env or {})}
        logger.info("Launching policy server for policy %s with command %s", policy_uri, cmd)
        process = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=log_file,
            env=child_env,
        )

    deadline = time.monotonic() + startup_timeout
    logger.info("Waiting for policy server to become ready for policy %s with deadline %s", policy_uri, deadline)
    _wait_for_ready_file(ready_file_path, process, log_path, deadline)

    port = int(ready_file_path.read_text().strip())
    logger.info("Policy server for policy %s ready on ws://127.0.0.1:%d (pid %d)", policy_uri, port, process.pid)
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
    log_tail = _read_log_tail(log_path)
    process.kill()
    process.wait()
    raise TimeoutError(f"Policy server did not become ready in time.\noutput:\n{log_tail}")
