from mettagrid.runner.episode_runner import _is_presigned_url


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
