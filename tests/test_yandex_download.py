from threading import Event
from types import SimpleNamespace

import pytest
import requests

from blackpearl.providers import yandex_music_provider
from blackpearl.providers.base import DownloadCancelled, DownloadOptions
from blackpearl.providers.yandex_music_provider import YandexMusicProvider

TRACK_URL = "https://music.yandex.ru/album/1/track/2"
DIRECT_LINK = "https://cdn.example/track.mp3"
CHUNKS = [b"a" * 10, b"b" * 10, b"c" * 10, b"d" * 10]


class FakeDownloadInfo:
    def __init__(self, bitrate, codec="mp3", preview=False):
        self.bitrate_in_kbps = bitrate
        self.codec = codec
        self.preview = preview
        self.client = SimpleNamespace(
            request=SimpleNamespace(proxies={"https": "http://proxy"})
        )
        self.direct_link_requested = False

    def get_direct_link(self):
        self.direct_link_requested = True
        return f"{DIRECT_LINK}?br={self.bitrate_in_kbps}"


class FakeResponse:
    def __init__(self, chunks, status_error=None, content_length=True):
        self._chunks = chunks
        self._status_error = status_error
        size = sum(len(chunk) for chunk in chunks)
        self.headers = {"Content-Length": str(size)} if content_length else {}

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def raise_for_status(self):
        if self._status_error is not None:
            raise self._status_error

    def iter_content(self, chunk_size):
        yield from self._chunks


def make_track(*infos):
    return SimpleNamespace(
        title="Song",
        artists=[SimpleNamespace(name="Artist")],
        get_download_info=lambda: list(infos),
    )


@pytest.fixture
def provider(monkeypatch):
    provider = YandexMusicProvider()
    tagged = []
    monkeypatch.setattr(
        provider,
        "_write_metadata",
        lambda track, path: tagged.append(path),
    )
    provider.tagged = tagged
    return provider


@pytest.fixture
def http(monkeypatch):
    """Подменяет requests.get и запоминает параметры запроса."""
    state = SimpleNamespace(response=FakeResponse(CHUNKS), calls=[])

    def fake_get(url, **kwargs):
        state.calls.append((url, kwargs))
        return state.response

    monkeypatch.setattr(yandex_music_provider.requests, "get", fake_get)
    return state


def test_download_streams_file_with_progress(provider, http, tmp_path, monkeypatch):
    info = FakeDownloadInfo(192)
    monkeypatch.setattr(provider, "_get_track", lambda url: make_track(info))
    progress = []

    provider.download(
        TRACK_URL,
        tmp_path,
        DownloadOptions(audio_bitrate_kbps=192),
        progress_callback=progress.append,
    )

    output = tmp_path / "Artist — Song.mp3"
    assert output.read_bytes() == b"".join(CHUNKS)
    assert not (tmp_path / "Artist — Song.mp3.part").exists()
    assert progress == [25.0, 50.0, 75.0, 100.0, 100.0]

    url, kwargs = http.calls[0]
    assert url == f"{DIRECT_LINK}?br=192"
    assert kwargs["stream"] is True
    assert kwargs["proxies"] == {"https": "http://proxy"}
    assert kwargs["timeout"] == YandexMusicProvider.HTTP_TIMEOUT
    # Теги пишутся во временный файл до переименования.
    assert [path.name for path in provider.tagged] == ["Artist — Song.mp3.part"]


def test_download_without_content_length_reports_only_final_progress(
    provider, http, tmp_path, monkeypatch
):
    http.response = FakeResponse(CHUNKS, content_length=False)
    monkeypatch.setattr(
        provider, "_get_track", lambda url: make_track(FakeDownloadInfo(192))
    )
    progress = []

    provider.download(
        TRACK_URL, tmp_path, DownloadOptions(), progress_callback=progress.append
    )

    assert progress == [100.0]
    assert (tmp_path / "Artist — Song.mp3").exists()


def test_cancel_mid_download_removes_partial_file(
    provider, http, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        provider, "_get_track", lambda url: make_track(FakeDownloadInfo(192))
    )
    cancel_event = Event()
    progress = []

    def on_progress(percent):
        progress.append(percent)
        cancel_event.set()  # Отмена после первой порции.

    with pytest.raises(DownloadCancelled):
        provider.download(
            TRACK_URL,
            tmp_path,
            DownloadOptions(),
            progress_callback=on_progress,
            cancel_event=cancel_event,
        )

    assert progress == [25.0]
    assert list(tmp_path.iterdir()) == []
    assert provider.tagged == []


def test_cancel_before_direct_link_skips_request(
    provider, http, tmp_path, monkeypatch
):
    info = FakeDownloadInfo(192)
    cancel_event = Event()

    def get_track(url):
        cancel_event.set()
        return make_track(info)

    monkeypatch.setattr(provider, "_get_track", get_track)

    with pytest.raises(DownloadCancelled):
        provider.download(
            TRACK_URL, tmp_path, DownloadOptions(), cancel_event=cancel_event
        )

    assert not info.direct_link_requested
    assert http.calls == []


def test_http_error_removes_partial_file(provider, http, tmp_path, monkeypatch):
    http.response = FakeResponse(
        [], status_error=requests.HTTPError("410 Gone")
    )
    monkeypatch.setattr(
        provider, "_get_track", lambda url: make_track(FakeDownloadInfo(192))
    )

    with pytest.raises(requests.HTTPError):
        provider.download(TRACK_URL, tmp_path, DownloadOptions())

    assert list(tmp_path.iterdir()) == []


def test_metadata_error_removes_partial_file(provider, http, tmp_path, monkeypatch):
    monkeypatch.setattr(
        provider, "_get_track", lambda url: make_track(FakeDownloadInfo(192))
    )

    def broken_metadata(track, path):
        raise OSError("disk full")

    monkeypatch.setattr(provider, "_write_metadata", broken_metadata)

    with pytest.raises(OSError):
        provider.download(TRACK_URL, tmp_path, DownloadOptions())

    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        (320, 320),
        (192, 192),
        (128, 128),
        (100, 128),  # ниже минимального — берём самый низкий
    ],
)
def test_select_download_info_picks_best_not_above_requested(requested, expected):
    track = make_track(
        FakeDownloadInfo(320),
        FakeDownloadInfo(128),
        FakeDownloadInfo(192),
        FakeDownloadInfo(320, preview=True),
        FakeDownloadInfo(256, codec="aac"),
    )

    info = YandexMusicProvider()._select_download_info(track, requested)

    assert info.bitrate_in_kbps == expected
    assert info.codec == "mp3"
    assert not info.preview


def test_select_download_info_without_mp3_fails():
    track = make_track(FakeDownloadInfo(256, codec="aac"))

    with pytest.raises(RuntimeError, match="MP3"):
        YandexMusicProvider()._select_download_info(track, 192)


def test_download_does_not_overwrite_track_with_same_name(
    provider, http, tmp_path, monkeypatch
):
    existing = tmp_path / "Artist — Song.mp3"
    existing.write_bytes(b"old")
    monkeypatch.setattr(
        provider, "_get_track", lambda url: make_track(FakeDownloadInfo(192))
    )

    provider.download(TRACK_URL, tmp_path, DownloadOptions())

    assert existing.read_bytes() == b"old"
    assert (tmp_path / "Artist — Song (2).mp3").read_bytes() == b"".join(CHUNKS)


def test_download_sanitizes_windows_unsafe_title(
    provider, http, tmp_path, monkeypatch
):
    track = make_track(FakeDownloadInfo(192))
    track.title = "What?."
    track.artists = []
    monkeypatch.setattr(provider, "_get_track", lambda url: track)

    provider.download(TRACK_URL, tmp_path, DownloadOptions())

    assert [path.name for path in tmp_path.iterdir()] == ["What_.mp3"]


class CountingClient:
    instances = 0

    def __init__(self, token):
        CountingClient.instances += 1
        self.token = token

    def init(self):
        return self


def test_client_is_created_once_and_reused(monkeypatch):
    CountingClient.instances = 0
    monkeypatch.setattr(yandex_music_provider, "Client", CountingClient)
    monkeypatch.setattr(
        yandex_music_provider,
        "settings",
        SimpleNamespace(yandex_music_token="token-1"),
    )
    provider = YandexMusicProvider()

    first = provider._get_client()
    second = provider._get_client()

    assert first is second
    assert CountingClient.instances == 1


def test_client_is_recreated_when_token_changes(monkeypatch):
    CountingClient.instances = 0
    monkeypatch.setattr(yandex_music_provider, "Client", CountingClient)
    monkeypatch.setattr(
        yandex_music_provider,
        "settings",
        SimpleNamespace(yandex_music_token="token-1"),
    )
    provider = YandexMusicProvider()
    first = provider._get_client()

    monkeypatch.setattr(
        yandex_music_provider,
        "settings",
        SimpleNamespace(yandex_music_token="token-2"),
    )
    second = provider._get_client()

    assert second is not first
    assert second.token == "token-2"


def test_client_requires_token(monkeypatch):
    monkeypatch.setattr(
        yandex_music_provider,
        "settings",
        SimpleNamespace(yandex_music_token=""),
    )

    with pytest.raises(RuntimeError, match="YANDEX_MUSIC_TOKEN"):
        YandexMusicProvider()._get_client()
