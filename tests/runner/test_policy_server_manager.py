import requests

from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.runner.policy_server_manager import launch_policy_server


def _minimal_env_interface() -> PolicyEnvInterface:
    return PolicyEnvInterface(
        obs_features=[],
        tags=[],
        action_names=["noop"],
        num_agents=1,
        observation_shape=(1, 3),
        egocentric_shape=(1, 1),
    )


def test_launch_health_and_shutdown():
    handle = launch_policy_server("mock://noop", _minimal_env_interface(), startup_timeout=15.0)
    try:
        assert handle.port > 0
        resp = requests.get(f"{handle.base_url}/health", timeout=5)
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
    finally:
        handle.shutdown()
    assert handle.process.returncode is not None
