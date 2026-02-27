"""Tests for RunnerError model and EpisodeSubprocessError exception."""

import json

import pytest
from pydantic import ValidationError

from mettagrid.runner.episode_runner import EpisodeSubprocessError
from mettagrid.runner.types import RunnerError


class TestRunnerError:
    def test_serialization_roundtrip(self):
        error = RunnerError(error_type="config_error", message="validation failed")
        raw = error.model_dump_json()
        parsed = RunnerError.model_validate_json(raw)
        assert parsed.error_type == "config_error"
        assert parsed.message == "validation failed"

    def test_all_valid_error_types(self):
        for error_type in ("config_error", "policy_error", "unknown"):
            error = RunnerError(error_type=error_type, message="test")
            assert error.error_type == error_type

    def test_invalid_error_type_rejected(self):
        with pytest.raises(ValidationError):
            RunnerError(error_type="bogus", message="test")

    def test_json_structure(self):
        error = RunnerError(error_type="policy_error", message="spawn failed")
        data = json.loads(error.model_dump_json())
        assert set(data.keys()) == {"error_type", "message"}
        assert data["error_type"] == "policy_error"


class TestEpisodeSubprocessError:
    def test_without_runner_error(self):
        err = EpisodeSubprocessError("subprocess failed (exit 1)")
        assert isinstance(err, RuntimeError)
        assert str(err) == "subprocess failed (exit 1)"
        assert err.runner_error is None

    def test_with_runner_error(self):
        runner_error = RunnerError(error_type="policy_error", message="step failed")
        err = EpisodeSubprocessError("subprocess failed (exit 1)", runner_error=runner_error)
        assert str(err) == "subprocess failed (exit 1)"
        assert err.runner_error is runner_error
        assert err.runner_error.error_type == "policy_error"

    def test_with_config_error(self):
        runner_error = RunnerError(error_type="config_error", message="validation failed")
        err = EpisodeSubprocessError("subprocess failed (exit 1)", runner_error=runner_error)
        assert err.runner_error.error_type == "config_error"
        assert err.runner_error.message == "validation failed"
