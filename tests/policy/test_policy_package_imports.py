"""Test that mettagrid.policy package exports are correct and all submodules are importable.

Note: The __init__.py intentionally contains no imports to avoid circular dependencies.
All imports should be done directly from submodules.
"""


def test_policy_package_exists():
    """Test that mettagrid.policy can be imported as a package."""
    import mettagrid.policy  # noqa: PLC0415

    assert hasattr(mettagrid.policy, "__path__"), "mettagrid.policy should be a package"


def test_core_policy_classes_importable():
    """Test that core policy classes can be imported from mettagrid.policy submodules."""
    # These are the most commonly used imports across the codebase
    from mettagrid.policy.policy import (  # noqa: PLC0415
        AgentPolicy,
        MultiAgentPolicy,
        NimMultiAgentPolicy,
        PolicySpec,
        StatefulAgentPolicy,
        StatefulPolicyImpl,
    )

    assert AgentPolicy is not None
    assert MultiAgentPolicy is not None
    assert NimMultiAgentPolicy is not None
    assert PolicySpec is not None
    assert StatefulAgentPolicy is not None
    assert StatefulPolicyImpl is not None


def test_policy_env_interface_importable():
    """Test that PolicyEnvInterface can be imported."""
    from mettagrid.policy.policy_env_interface import PolicyEnvInterface  # noqa: PLC0415

    assert PolicyEnvInterface is not None


def test_policy_loader_utilities_importable():
    """Test that policy loader utilities can be imported."""
    from mettagrid.policy.loader import (  # noqa: PLC0415
        discover_and_register_policies,
        initialize_or_load_policy,
        resolve_policy_class_path,
    )

    assert discover_and_register_policies is not None
    assert initialize_or_load_policy is not None
    assert resolve_policy_class_path is not None


def test_policy_registry_importable():
    """Test that policy registry can be imported."""
    from mettagrid.policy.policy_registry import get_policy_registry  # noqa: PLC0415

    assert get_policy_registry is not None
    # Should return a dict
    assert isinstance(get_policy_registry(), dict)


def test_submission_utilities_importable():
    """Test that submission utilities can be imported."""
    from mettagrid.policy.submission import POLICY_SPEC_FILENAME, SubmissionPolicySpec  # noqa: PLC0415

    assert POLICY_SPEC_FILENAME == "policy_spec.json"
    assert SubmissionPolicySpec is not None


def test_prepare_policy_spec_importable():
    """Test that prepare_policy_spec utilities can be imported."""
    from mettagrid.policy.prepare_policy_spec import download_policy_spec_from_s3_as_zip  # noqa: PLC0415

    assert download_policy_spec_from_s3_as_zip is not None


def test_policy_implementations_importable():
    """Test that common policy implementations can be imported."""
    from mettagrid.policy.lstm import LSTMPolicy  # noqa: PLC0415
    from mettagrid.policy.noop import NoopPolicy  # noqa: PLC0415
    from mettagrid.policy.pufferlib import PufferlibStatefulImpl  # noqa: PLC0415
    from mettagrid.policy.random_agent import RandomMultiAgentPolicy  # noqa: PLC0415

    assert RandomMultiAgentPolicy is not None
    assert LSTMPolicy is not None
    assert NoopPolicy is not None
    assert PufferlibStatefulImpl is not None


def test_token_encoder_importable():
    """Test that token encoder utilities can be imported."""
    from mettagrid.policy.token_encoder import coordinates  # noqa: PLC0415

    assert coordinates is not None


def test_no_circular_import_with_config():
    """Test that importing policy doesn't create circular import with config."""
    # This import chain previously caused circular imports:
    # config -> simulator -> util.file -> policy -> config
    from mettagrid.config.mettagrid_c_config import convert_to_cpp_game_config  # noqa: PLC0415
    from mettagrid.policy.policy import MultiAgentPolicy  # noqa: PLC0415

    assert convert_to_cpp_game_config is not None
    assert MultiAgentPolicy is not None
