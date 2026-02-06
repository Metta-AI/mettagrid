import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from mettagrid.runner.policy_server.manager import launch_local_policy_server


def _fake_create_policy_venv(mettagrid_version: str, requires_python: str) -> Path:
    policy_dir = Path(tempfile.mkdtemp(prefix="policy-test-"))
    bin_dir = policy_dir / ".venv" / "bin"
    bin_dir.mkdir(parents=True)
    wrapper = bin_dir / "python"
    wrapper.write_text(f'#!/bin/sh\nexec {sys.executable} "$@"\n')
    wrapper.chmod(0o755)
    return policy_dir


@patch(
    "mettagrid.runner.policy_server.manager._get_mettagrid_source",
    return_value=("mettagrid==0.0.0", ">=3.11"),
)
@patch(
    "mettagrid.runner.policy_server.manager._create_policy_venv",
    side_effect=_fake_create_policy_venv,
)
class TestLaunchLocalPolicyServer:
    def test_launch_and_shutdown(self, _mock_venv, _mock_pypi):
        handle = launch_local_policy_server("mock://noop", startup_timeout=15.0)
        try:
            assert handle.port > 0
            assert handle.base_url.startswith("ws://")
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

    def test_shutdown_cleans_up_ready_file(self, _mock_venv, _mock_pypi):
        handle = launch_local_policy_server("mock://noop", startup_timeout=15.0)
        ready_file = handle._ready_file_path
        assert ready_file is not None
        assert ready_file.exists()
        handle.shutdown()
        assert not ready_file.exists()
