import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import requests

from mettagrid.runner.policy_server.manager import launch_local_policy_server


def _fake_create_policy_venv(mettagrid_version: str, requires_python: str) -> Path:
    # Shell wrapper instead of symlink so the real python resolves its own pyvenv.cfg and site-packages.
    policy_dir = Path(tempfile.mkdtemp(prefix="policy-test-"))
    bin_dir = policy_dir / ".venv" / "bin"
    bin_dir.mkdir(parents=True)
    wrapper = bin_dir / "python"
    wrapper.write_text(f'#!/bin/sh\nexec {sys.executable} "$@"\n')
    wrapper.chmod(0o755)
    return policy_dir


@patch(
    "mettagrid.runner.policy_server.manager._get_latest_pypi_info",
    return_value=("0.0.0", ">=3.11"),
)
@patch(
    "mettagrid.runner.policy_server.manager._create_policy_venv",
    side_effect=_fake_create_policy_venv,
)
class TestLaunchLocalPolicyServer:
    def test_launch_health_and_shutdown(self, _mock_venv, _mock_pypi):
        handle = launch_local_policy_server("mock://noop", startup_timeout=15.0)
        try:
            assert handle.port > 0
            resp = requests.get(f"{handle.base_url}/health", timeout=5)
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}
        finally:
            handle.shutdown()
        assert handle.process.returncode is not None

    def test_read_logs_captures_server_output(self, _mock_venv, _mock_pypi):
        handle = launch_local_policy_server("mock://noop", startup_timeout=15.0)
        try:
            logs = handle.read_logs()
            assert len(logs) > 0, "Expected non-empty logs from policy server"
        finally:
            handle.shutdown()

    def test_read_logs_captures_errors(self, _mock_venv, _mock_pypi):
        handle = launch_local_policy_server("mock://noop", startup_timeout=15.0)
        try:
            resp = requests.post(
                f"{handle.base_url}/mettagrid.protobuf.sim.policy_v1.Policy/PreparePolicy",
                data=b"not valid json",
                timeout=5,
            )
            assert resp.status_code == 400
            logs = handle.read_logs()
            assert len(logs) > 0, "Expected logs to contain server output after error"
        finally:
            handle.shutdown()
