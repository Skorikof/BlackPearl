import sys
from pathlib import Path

import pytest

from blackpearl.core import ffmpeg
from blackpearl.providers import yt_dlp_provider
from blackpearl.providers.base import DownloadOptions, MediaInfo, MediaProvider
from blackpearl.providers.registry import ProviderRegistry
from blackpearl.providers.yandex_music_provider import YandexMusicProvider
from blackpearl.providers.yt_dlp_provider import YtDlpProvider


class FakeYoutubeDL:
    """Подменяет yt_dlp.YoutubeDL и запоминает переданные опции."""

    last_options: dict | None = None

    def __init__(self, options: dict) -> None:
        FakeYoutubeDL.last_options = options

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def download(self, urls):
        pass


@pytest.fixture
def fake_ydl(monkeypatch):
    FakeYoutubeDL.last_options = None
    monkeypatch.setattr(yt_dlp_provider.yt_dlp, "YoutubeDL", FakeYoutubeDL)
    monkeypatch.setattr(
        yt_dlp_provider, "require_ffmpeg", lambda: "C:/tools/ffmpeg.exe"
    )
    return FakeYoutubeDL


def test_yt_dlp_audio_extracts_mp3_with_requested_bitrate(fake_ydl, tmp_path):
    YtDlpProvider().download(
        "https://youtube.com/watch?v=1",
        tmp_path,
        DownloadOptions(kind="audio", audio_bitrate_kbps=320),
    )

    options = fake_ydl.last_options
    assert options["format"] == "bestaudio/best"
    assert options["ffmpeg_location"] == "C:/tools/ffmpeg.exe"
    assert options["postprocessors"] == [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "320",
        }
    ]
    assert options["paths"] == {"home": str(tmp_path)}


def test_yt_dlp_video_limits_height_and_merges_to_mp4(fake_ydl, tmp_path):
    YtDlpProvider().download(
        "https://youtube.com/watch?v=1",
        tmp_path,
        DownloadOptions(kind="video", video_max_height=720),
    )

    options = fake_ydl.last_options
    assert options["format"] == (
        "bestvideo[height<=720]+bestaudio/best[height<=720]"
    )
    assert options["merge_output_format"] == "mp4"
    assert "postprocessors" not in options


def test_yt_dlp_video_without_height_limit(fake_ydl, tmp_path):
    YtDlpProvider().download(
        "https://youtube.com/watch?v=1",
        tmp_path,
        DownloadOptions(kind="video"),
    )

    assert fake_ydl.last_options["format"] == "bestvideo+bestaudio/best"


def test_yt_dlp_fails_before_download_without_ffmpeg(monkeypatch, tmp_path):
    def fail():
        raise ffmpeg.FfmpegNotFoundError()

    monkeypatch.setattr(yt_dlp_provider, "require_ffmpeg", fail)

    def unexpected(*args, **kwargs):
        raise AssertionError("yt-dlp не должен запускаться без ffmpeg")

    monkeypatch.setattr(yt_dlp_provider.yt_dlp, "YoutubeDL", unexpected)

    with pytest.raises(ffmpeg.FfmpegNotFoundError, match="ffmpeg"):
        YtDlpProvider().download(
            "https://youtube.com/watch?v=1",
            tmp_path / "out",
            DownloadOptions(kind="audio"),
        )
    assert not (tmp_path / "out").exists()


def test_find_ffmpeg_prefers_path(monkeypatch):
    monkeypatch.setattr(ffmpeg.shutil, "which", lambda name: "/usr/bin/ffmpeg")

    assert ffmpeg.find_ffmpeg() == "/usr/bin/ffmpeg"


def test_find_ffmpeg_returns_none_when_nothing_available(monkeypatch):
    monkeypatch.setattr(ffmpeg.shutil, "which", lambda name: None)
    # None в sys.modules заставляет import бросить ImportError.
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)

    assert ffmpeg.find_ffmpeg() is None
    with pytest.raises(ffmpeg.FfmpegNotFoundError):
        ffmpeg.require_ffmpeg()


def test_yandex_supports_only_audio():
    provider = YandexMusicProvider()

    assert provider.supports("audio")
    assert not provider.supports("video")


def test_yandex_download_rejects_video(tmp_path):
    with pytest.raises(ValueError, match="только аудио"):
        YandexMusicProvider().download(
            "https://music.yandex.ru/album/1/track/2",
            tmp_path,
            DownloadOptions(kind="video"),
        )


class AudioOnlyProvider(MediaProvider):
    supported_kinds = frozenset({"audio"})

    def can_handle(self, url: str) -> bool:
        return True

    def get_info(self, url: str) -> MediaInfo:
        return MediaInfo(title="", url=url, media_type="audio")

    def download(self, url, output_dir: Path, options, **kwargs) -> None:
        pass


class AnyProvider(AudioOnlyProvider):
    supported_kinds = frozenset({"audio", "video"})


def test_registry_filters_providers_by_kind():
    audio_only = AudioOnlyProvider()
    universal = AnyProvider()
    registry = ProviderRegistry()
    registry.register(audio_only)
    registry.register(universal)

    url = "https://example.com/media"
    assert registry.get_provider(url) is audio_only
    assert registry.get_provider(url, kind="audio") is audio_only
    assert registry.get_provider(url, kind="video") is universal


def test_registry_returns_none_when_kind_unsupported():
    registry = ProviderRegistry()
    registry.register(AudioOnlyProvider())

    assert registry.get_provider("https://example.com/x", kind="video") is None
