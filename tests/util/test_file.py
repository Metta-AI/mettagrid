from urllib.parse import parse_qs, urlparse

import boto3
import pytest
from botocore.config import Config

from mettagrid.util.file import _is_presigned_s3_url


@pytest.fixture
def fake_aws_credentials(monkeypatch):
    """Set fake AWS credentials for boto3 (required for presigned URL generation)."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


def test_boto3_default_presigned_url_is_detected(fake_aws_credentials):
    """Verify boto3 default presigned URLs are detected (regardless of signature version)."""
    s3 = boto3.client("s3")
    url = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": "test-bucket",
            "Key": "test-key.zip",
            "ContentType": "application/zip",
        },
        ExpiresIn=3600,
    )
    assert _is_presigned_s3_url(url), f"_is_presigned_s3_url should detect presigned URL: {url}"


def test_boto3_sigv4_presigned_url_is_detected(fake_aws_credentials):
    """Verify boto3 with signature_version=s3v4 generates detectable SigV4 presigned URLs."""
    s3 = boto3.client("s3", config=Config(signature_version="s3v4"))
    url = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": "test-bucket",
            "Key": "test-key.zip",
            "ContentType": "application/zip",
        },
        ExpiresIn=3600,
    )
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)

    # Verify it's actually SigV4
    assert "X-Amz-Algorithm" in query_params, (
        f"Expected SigV4 presigned URL with X-Amz-Algorithm, got query params: {list(query_params.keys())}"
    )

    # Verify _is_presigned_s3_url detects it
    assert _is_presigned_s3_url(url), f"_is_presigned_s3_url should detect SigV4 URL: {url}"


def test_is_presigned_s3_url_with_sigv4():
    url = "https://bucket.s3.amazonaws.com/key?X-Amz-Algorithm=AWS4-HMAC-SHA256"
    assert _is_presigned_s3_url(url)


def test_is_presigned_s3_url_with_sigv2():
    url = "https://bucket.s3.amazonaws.com/key?AWSAccessKeyId=AKIAIOSFODNN7EXAMPLE&Signature=xyz"
    assert _is_presigned_s3_url(url)


def test_is_presigned_s3_url_with_s3_scheme():
    assert not _is_presigned_s3_url("s3://bucket/key")


def test_is_presigned_s3_url_with_plain_https():
    assert not _is_presigned_s3_url("https://example.com/file")


def test_is_presigned_s3_url_with_file_scheme():
    assert not _is_presigned_s3_url("file:///tmp/foo")


def test_is_presigned_s3_url_with_http():
    # http presigned URLs are valid (e.g. localstack in local dev)
    assert _is_presigned_s3_url("http://bucket.s3.amazonaws.com/key?X-Amz-Algorithm=AWS4-HMAC-SHA256")
