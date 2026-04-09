import shutil
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from mettagrid.runner.episode_runner import (
    _compact_policy_names,
    _download_presigned_policy,
    _is_builtin_or_classpath_metta_policy_uri,
    _is_presigned_url,
    _localize_policy_uri,
    _per_agent_policy_mapping,
    _spawn_policy_servers,
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
    uris, remapped_assignments, index_remap = _per_agent_policy_mapping(
        ["file:///policy0.zip", "file:///policy1.zip", "file:///policy2.zip"],
        assignments=[0, 0, 2, 2, 0, 2],
        num_agents=6,
    )

    assert uris == ["file:///policy0.zip", "file:///policy2.zip"]
    assert remapped_assignments == [0, 0, 1, 1, 0, 1]
    assert index_remap == {0: 0, 2: 1}


def test_per_agent_policy_mapping_keeps_distinct_duplicate_indices() -> None:
    uris, remapped_assignments, index_remap = _per_agent_policy_mapping(
        ["file:///same.zip", "file:///same.zip"],
        assignments=[0, 1, 0, 1],
        num_agents=4,
    )

    assert uris == ["file:///same.zip", "file:///same.zip"]
    assert remapped_assignments == [0, 1, 0, 1]
    assert index_remap == {0: 0, 1: 1}


def test_compact_policy_names_follows_policy_index_remap() -> None:
    compact_names = _compact_policy_names(
        ["alpha:v7", "beta:v3", "gamma:v2"],
        policy_index_remap={0: 0, 2: 1},
    )

    assert compact_names == ["alpha:v7", "gamma:v2"]


def test_compact_policy_names_returns_none_when_unset() -> None:
    assert _compact_policy_names(None, policy_index_remap={0: 0}) is None


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


class TestSpawnPolicyServersSecretsInjection:
    """Verify that per-policy secrets are threaded to the correct policy server."""

    def _make_handle(self, port: int) -> MagicMock:
        handle = MagicMock()
        handle.base_url = f"ws://127.0.0.1:{port}"
        return handle

    def test_passes_correct_extra_env_per_policy(self) -> None:
        secrets = {0: {"ANTHROPIC_API_KEY": "sk-policy0"}, 1: {"ANTHROPIC_API_KEY": "sk-policy1"}}
        uris = ["file:///policy0.zip", "file:///policy1.zip"]

        with patch(
            "mettagrid.runner.episode_runner.launch_local_policy_server",
            side_effect=[self._make_handle(9000), self._make_handle(9001)],
        ) as mock_launch:
            _spawn_policy_servers(uris, per_policy_envs=secrets)

        assert mock_launch.call_count == 2
        calls = mock_launch.call_args_list
        assert calls[0] == call("file:///policy0.zip", extra_env={"ANTHROPIC_API_KEY": "sk-policy0"})
        assert calls[1] == call("file:///policy1.zip", extra_env={"ANTHROPIC_API_KEY": "sk-policy1"})

    def test_passes_none_extra_env_when_no_secrets_for_policy(self) -> None:
        """Policy index 1 has no secrets — extra_env should be None."""
        secrets = {0: {"API_KEY": "abc"}}
        uris = ["file:///policy0.zip", "file:///policy1.zip"]

        with patch(
            "mettagrid.runner.episode_runner.launch_local_policy_server",
            side_effect=[self._make_handle(9000), self._make_handle(9001)],
        ) as mock_launch:
            _spawn_policy_servers(uris, per_policy_envs=secrets)

        calls = mock_launch.call_args_list
        assert calls[0] == call("file:///policy0.zip", extra_env={"API_KEY": "abc"})
        assert calls[1] == call("file:///policy1.zip", extra_env=None)

    def test_no_secrets_passes_none_for_all(self) -> None:
        uris = ["file:///policy0.zip", "file:///policy1.zip"]

        with patch(
            "mettagrid.runner.episode_runner.launch_local_policy_server",
            side_effect=[self._make_handle(9000), self._make_handle(9001)],
        ) as mock_launch:
            _spawn_policy_servers(uris, per_policy_envs=None)

        calls = mock_launch.call_args_list
        assert calls[0] == call("file:///policy0.zip", extra_env=None)
        assert calls[1] == call("file:///policy1.zip", extra_env=None)


def test_secrets_remap_follows_policy_index_remap() -> None:
    """Secrets keyed by original policy index are remapped to compact indices."""
    # Original indices: policy 0 used by agents 0,1; policy 2 used by agents 2,3.
    # Compact mapping: 0→0, 2→1.
    _, _, index_remap = _per_agent_policy_mapping(
        ["file:///p0.zip", "file:///p1.zip", "file:///p2.zip"],
        assignments=[0, 0, 2, 2],
        num_agents=4,
    )
    assert index_remap == {0: 0, 2: 1}

    policy_secrets = {0: {"KEY_A": "val0"}, 2: {"KEY_A": "val2"}}
    compact_secrets = {
        compact_idx: policy_secrets[orig_idx]
        for orig_idx, compact_idx in index_remap.items()
        if orig_idx in policy_secrets
    }
    assert compact_secrets == {0: {"KEY_A": "val0"}, 1: {"KEY_A": "val2"}}


def test_secrets_remap_drops_policies_with_no_secrets() -> None:
    """Compact secrets only includes policies that actually have secrets."""
    _, _, index_remap = _per_agent_policy_mapping(
        ["file:///p0.zip", "file:///p1.zip"],
        assignments=[0, 1, 0, 1],
        num_agents=4,
    )
    assert index_remap == {0: 0, 1: 1}

    policy_secrets = {0: {"API_KEY": "abc"}}  # only policy 0 has secrets
    compact_secrets = {
        compact_idx: policy_secrets[orig_idx]
        for orig_idx, compact_idx in index_remap.items()
        if orig_idx in policy_secrets
    }
    assert compact_secrets == {0: {"API_KEY": "abc"}}
    assert 1 not in compact_secrets


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
