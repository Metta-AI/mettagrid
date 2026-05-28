"""Tests for RunnerError model."""

import json

import pytest
from pydantic import ValidationError

from mettagrid.runner.types import RunnerError


class TestRunnerError:
    def test_serialization_roundtrip(self):
        error = RunnerError(error_type="config_error", message="validation failed")
        raw = error.model_dump_json()
        parsed = RunnerError.model_validate_json(raw)
        assert parsed.error_type == "config_error"
        assert parsed.message == "validation failed"

    def test_all_valid_error_types(self):
        for error_type in ("config_error", "policy_error", "crash", "unknown"):
            error = RunnerError(error_type=error_type, message="test")
            assert error.error_type == error_type

    def test_invalid_error_type_rejected(self):
        with pytest.raises(ValidationError):
            RunnerError(error_type="bogus", message="test")

    def test_json_structure(self):
        error = RunnerError(error_type="policy_error", message="spawn failed")
        data = json.loads(error.model_dump_json())
        assert {"error_type", "message"} <= set(data.keys())
        assert data["error_type"] == "policy_error"

    def test_json_structure_with_policy_attribution(self):
        error = RunnerError(
            error_type="policy_error",
            message="step failed",
            failed_policy_index=1,
            failed_policy_uri="file:///policies/bad.zip",
            failed_policy_name="bad-policy:v1",
        )
        data = json.loads(error.model_dump_json())
        assert data["failed_policy_index"] == 1
        assert data["failed_policy_uri"] == "file:///policies/bad.zip"
        assert data["failed_policy_name"] == "bad-policy:v1"

    def test_roundtrip_with_policy_attribution(self):
        error = RunnerError(
            error_type="policy_error",
            message="ws failed",
            failed_policy_index=0,
            failed_policy_uri="metta://policy/random",
            failed_policy_name="random",
        )
        parsed = RunnerError.model_validate_json(error.model_dump_json())
        assert parsed.failed_policy_index == 0
        assert parsed.failed_policy_uri == "metta://policy/random"
        assert parsed.failed_policy_name == "random"

    def test_roundtrip_without_policy_attribution(self):
        """Old-format error_info.json (no policy fields) still parses cleanly."""
        raw = '{"error_type": "crash", "message": "boom"}'
        parsed = RunnerError.model_validate_json(raw)
        assert parsed.failed_policy_index is None
        assert parsed.failed_policy_uri is None
        assert parsed.failed_policy_name is None
