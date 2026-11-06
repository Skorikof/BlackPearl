from blackpearl.providers.yt_dlp_provider import YtDlpProvider


def test_provider_accepts_http_url():
    provider = YtDlpProvider()
    assert provider.can_handle("https://youtube.com/watch?v=123")


def test_provider_accepts_https_url():
    provider = YtDlpProvider()
    assert provider.can_handle("http://example.com/video")


def test_provider_rejects_non_http_url():
    provider = YtDlpProvider()
    assert not provider.can_handle("ftp://example.com/video")


def test_provider_rejects_invalid_url():
    provider = YtDlpProvider()
    assert not provider.can_handle("not a url")
