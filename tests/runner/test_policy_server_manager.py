import requests

from mettagrid.runner.policy_server.manager import launch_local_policy_server


def test_launch_health_and_shutdown():
    handle = launch_local_policy_server("mock://noop", startup_timeout=15.0)
    try:
        assert handle.port > 0
        resp = requests.get(f"{handle.base_url}/health", timeout=5)
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
    finally:
        handle.shutdown()
    assert handle.process.returncode is not None


def test_read_logs_captures_server_output():
    handle = launch_local_policy_server("mock://noop", startup_timeout=15.0)
    try:
        logs = handle.read_logs()
        assert len(logs) > 0, "Expected non-empty logs from policy server"
    finally:
        handle.shutdown()


def test_read_logs_captures_errors():
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
