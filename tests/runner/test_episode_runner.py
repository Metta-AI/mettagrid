import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mettagrid.runner.episode_runner import (
    _download_presigned_policy,
    _is_builtin_or_classpath_metta_policy_uri,
    _is_presigned_url,
    _localize_policy_uri,
    _per_agent_policy_mapping,
    _to_file_uri,
)


class TestIsPresignedUrl:
    def test_sigv4_presigned(self):
        url = "https://my-bucket.s3.amazonaws.com/key?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIA..."
        assert _is_presigned_url(url) is True

    def test_sigv2_presigned(self):
        url = "https://my-bucket.s3.amazonaws.com/key?AWSAccessKeyId=AKIA123&Signature=abc&Expires=999"
        assert _is_presigned_url(url) is True

    def test_regular_https(self):
        url = "https://example.com/some/path"
        assert _is_presigned_url(url) is False

    def test_s3_scheme(self):
        url = "s3://my-bucket/my-key"
        assert _is_presigned_url(url) is False


def test_to_file_uri_resolves_relative_paths() -> None:
    relative_path = Path("train_dir/replay.json.z")

    assert _to_file_uri(relative_path) == relative_path.resolve().as_uri()


def test_per_agent_policy_mapping_compacts_by_policy_index() -> None:
    uris, remapped_assignments = _per_agent_policy_mapping(
        ["file:///policy0.zip", "file:///policy1.zip", "file:///policy2.zip"],
        assignments=[0, 0, 2, 2, 0, 2],
        num_agents=6,
    )

    assert uris == ["file:///policy0.zip", "file:///policy2.zip"]
    assert remapped_assignments == [0, 0, 1, 1, 0, 1]


def test_per_agent_policy_mapping_keeps_distinct_duplicate_indices() -> None:
    uris, remapped_assignments = _per_agent_policy_mapping(
        ["file:///same.zip", "file:///same.zip"],
        assignments=[0, 1, 0, 1],
        num_agents=4,
    )

    assert uris == ["file:///same.zip", "file:///same.zip"]
    assert remapped_assignments == [0, 1, 0, 1]


def test_per_agent_policy_mapping_rejects_bad_assignments() -> None:
    with pytest.raises(ValueError, match="Assignments must match agent count and be within policy range"):
        _per_agent_policy_mapping(
            ["file:///policy0.zip"],
            assignments=[0, 1],
            num_agents=2,
        )


def test_is_builtin_or_classpath_metta_policy_uri_detects_builtin_policy() -> None:
    assert _is_builtin_or_classpath_metta_policy_uri("metta://policy/random")


def test_localize_policy_uri_preserves_builtin_metta_policy_uri() -> None:
    with patch("mettagrid.runner.episode_runner.localize_uri") as mock_localize:
        uri = "metta://policy/random?vibe_action_p=0.01"
        assert _localize_policy_uri(uri, temp_dirs=[]) == uri
        mock_localize.assert_not_called()


def test_localize_policy_uri_still_localizes_non_builtin_uris() -> None:
    with (
        patch("mettagrid.runner.episode_runner._is_builtin_or_classpath_metta_policy_uri", return_value=False),
        patch("mettagrid.runner.episode_runner.resolve_uri") as mock_resolve,
        patch("mettagrid.runner.episode_runner.localize_uri", return_value=Path("/tmp/policy.zip")) as mock_localize,
    ):
        mock_resolve.return_value = type("Resolved", (), {"scheme": "metta", "canonical": "metta://policy/x"})()
        assert _localize_policy_uri("metta://policy/not_builtin:v1", temp_dirs=[]) == "file:///tmp/policy.zip"
        mock_localize.assert_called_once()


class TestDownloadPresignedPolicy:
    """Tests for streaming download with size guard."""

    def _mock_response(self, chunk_size: int, num_chunks: int) -> MagicMock:
        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        mock.iter_content.return_value = [b"x" * chunk_size] * num_chunks
        return mock

    MOCK_LIMIT = 1 * 1024 * 1024  # 1MB — small enough for fast tests

    def test_rejects_oversized_policy(self) -> None:
        # 2MB total, 1MB limit → should fail
        mock_resp = self._mock_response(chunk_size=1024, num_chunks=2048)
        temp_dirs: list[Path] = []

        with patch("mettagrid.runner.episode_runner.requests.get", return_value=mock_resp):
            with patch("mettagrid.runner.episode_runner.MAX_POLICY_SIZE_BYTES", self.MOCK_LIMIT):
                with pytest.raises(ValueError, match="exceeds 1 MB limit"):
                    _download_presigned_policy("https://example.com/policy.zip", temp_dirs)

        for d in temp_dirs:
            shutil.rmtree(d, ignore_errors=True)

    def test_succeeds_under_limit(self) -> None:
        # 512KB total, 1MB limit → should succeed
        mock_resp = self._mock_response(chunk_size=1024, num_chunks=512)
        temp_dirs: list[Path] = []

        with patch("mettagrid.runner.episode_runner.requests.get", return_value=mock_resp):
            with patch("mettagrid.runner.episode_runner.MAX_POLICY_SIZE_BYTES", self.MOCK_LIMIT):
                result = _download_presigned_policy("https://example.com/policy.zip", temp_dirs)

        assert result.exists()
        assert result.stat().st_size == 512 * 1024

        for d in temp_dirs:
            shutil.rmtree(d, ignore_errors=True)

    def test_streams_instead_of_buffering(self) -> None:
        """Verify stream=True is passed to requests.get."""
        mock_resp = self._mock_response(chunk_size=1024, num_chunks=1)
        temp_dirs: list[Path] = []

        with patch("mettagrid.runner.episode_runner.requests.get", return_value=mock_resp) as mock_get:
            with patch("mettagrid.runner.episode_runner.MAX_POLICY_SIZE_BYTES", self.MOCK_LIMIT):
                _download_presigned_policy("https://example.com/policy.zip", temp_dirs)

        mock_get.assert_called_once_with("https://example.com/policy.zip", timeout=30, stream=True)

        for d in temp_dirs:
            shutil.rmtree(d, ignore_errors=True)
