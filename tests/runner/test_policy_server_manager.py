import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from mettagrid.runner.policy_server.manager import (
    _find_package_root,
    _get_mettagrid_source,
    launch_local_policy_server,
)


def _fake_create_policy_venv() -> Path:
    policy_dir = Path(tempfile.mkdtemp(prefix="policy-test-"))
    bin_dir = policy_dir / ".venv" / "bin"
    bin_dir.mkdir(parents=True)
    wrapper = bin_dir / "python"
    wrapper.write_text(f'#!/bin/sh\nexec {sys.executable} "$@"\n')
    wrapper.chmod(0o755)
    return policy_dir


class TestFindPackageRoot:
    def test_finds_pyproject_toml(self, tmp_path: Path):
        pkg_dir = tmp_path / "src" / "mypkg"
        pkg_dir.mkdir(parents=True)
        (tmp_path / "pyproject.toml").touch()
        assert _find_package_root(pkg_dir) == tmp_path.resolve()

    def test_returns_none_without_pyproject(self, tmp_path: Path):
        pkg_dir = tmp_path / "site-packages" / "mypkg"
        pkg_dir.mkdir(parents=True)
        assert _find_package_root(pkg_dir) is None


class TestGetMettagridSource:
    def test_local_source_returns_path(self):
        source = _get_mettagrid_source()
        # In dev, this should be a local path (not a version pin)
        assert not source.startswith("mettagrid==")
        assert Path(source).is_dir()
        assert (Path(source) / "pyproject.toml").exists()

    def test_site_packages_returns_version_pin(self, tmp_path: Path):
        fake_pkg = tmp_path / "site-packages" / "mettagrid"
        fake_pkg.mkdir(parents=True)
        (fake_pkg / "__init__.py").write_text("__path__ = []\n")
        with patch("mettagrid.__path__", [str(fake_pkg)]):
            source = _get_mettagrid_source()
        assert source.startswith("mettagrid==")


@patch.dict(os.environ, {"EPISODE_RUNNER_USE_ISOLATED_VENVS": "1"})
@patch(
    "mettagrid.runner.policy_server.manager._get_mettagrid_source",
    return_value="mettagrid==0.0.0",
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
