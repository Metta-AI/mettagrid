from mettagrid.runner.executor import _collect_runtime_info


def test_collect_runtime_info_includes_git_and_cogames_version() -> None:
    runtime_info = _collect_runtime_info("abc1234", "0.5.0")

    assert runtime_info.git_commit == "abc1234"
    assert runtime_info.cogames_version == "0.5.0"
