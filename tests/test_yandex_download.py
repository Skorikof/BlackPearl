import sys
from threading import Event
from types import SimpleNamespace

import pytest
import requests

from blackpearl.core.track_metadata import TrackMetadata, write_tags
from blackpearl.providers import yandex_music_provider
from blackpearl.providers.base import (
    DownloadCancelled,
    DownloadOptions,
    DownloadOutcome,
)
from blackpearl.providers.yandex_music_provider import YandexMusicProvider
from tests.test_track_metadata import make_flac

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


def make_track(*infos, albums=()):
    return SimpleNamespace(
        id=2,
        title="Song",
        version=None,
        artists=[SimpleNamespace(name="Artist")],
        albums=list(albums),
        cover_uri=None,
        get_download_info=lambda: list(infos),
    )


@pytest.fixture
def provider(monkeypatch):
    provider = YandexMusicProvider()
    tagged = []
    monkeypatch.setattr(
        provider,
        "_write_metadata",
        lambda track, album, metadata, path, audio_format: tagged.append(path),
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

    def broken_metadata(track, album, metadata, path, audio_format):
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


def make_album(album_id=10, **fields):
    defaults = dict(
        id=album_id,
        title="Album",
        version=None,
        artists=[SimpleNamespace(name="Artist", various=False)],
        type=None,
        year=2020,
        original_release_year=None,
        genre="rock",
        track_position=SimpleNamespace(volume=1, index=3),
        cover_uri=None,
    )
    defaults.update(fields)
    return SimpleNamespace(**defaults)


def test_build_metadata_from_album():
    track = make_track(albums=[make_album()])
    track.version = "Live"

    metadata = YandexMusicProvider._build_metadata(track, track.albums[0])

    assert metadata.source_id == "yandex:2"
    assert metadata.title == "Song (Live)"
    assert metadata.artists == ["Artist"]
    assert metadata.album_title == "Album"
    assert metadata.album_artist == "Artist"
    assert metadata.year == 2020
    assert metadata.genre == "rock"
    assert (metadata.disc_number, metadata.track_number) == (1, 3)


def test_build_metadata_uses_original_year_and_album_version():
    album = make_album(year=None, original_release_year=1999, version="Deluxe")

    metadata = YandexMusicProvider._build_metadata(make_track(), album)

    assert metadata.year == 1999
    assert metadata.album_title == "Album (Deluxe)"


@pytest.mark.parametrize(
    "album",
    [
        make_album(type="compilation"),
        make_album(artists=[SimpleNamespace(name="Сборник", various=True)]),
        make_album(artists=[]),
    ],
)
def test_build_metadata_marks_compilations_as_various_artists(album):
    metadata = YandexMusicProvider._build_metadata(make_track(), album)

    assert metadata.album_artist == "Various Artists"


def test_build_metadata_without_album():
    metadata = YandexMusicProvider._build_metadata(make_track(), None)

    assert metadata.album_title is None
    assert metadata.track_number is None


def test_choose_album_prefers_album_from_url():
    original, compilation = make_album(10), make_album(20)
    track = make_track(albums=[original, compilation])

    assert YandexMusicProvider._choose_album(track, "20") is compilation
    assert YandexMusicProvider._choose_album(track, "99") is original
    assert YandexMusicProvider._choose_album(track, None) is original
    assert YandexMusicProvider._choose_album(make_track(), "10") is None


def test_download_organizes_by_album(provider, http, tmp_path, monkeypatch):
    track = make_track(FakeDownloadInfo(192), albums=[make_album()])
    monkeypatch.setattr(provider, "_get_track", lambda url: track)

    outcome = provider.download(
        "https://music.yandex.ru/album/10/track/2", tmp_path, DownloadOptions()
    )

    expected = tmp_path / "Artist" / "Album (2020)" / "03 - Song.mp3"
    assert outcome is DownloadOutcome.DOWNLOADED
    assert expected.read_bytes() == b"".join(CHUNKS)


def test_download_flat_when_organizing_disabled(provider, http, tmp_path, monkeypatch):
    track = make_track(FakeDownloadInfo(192), albums=[make_album()])
    monkeypatch.setattr(provider, "_get_track", lambda url: track)

    provider.download(
        TRACK_URL, tmp_path, DownloadOptions(organize_by_album=False)
    )

    assert [path.name for path in tmp_path.iterdir()] == ["Artist — Song.mp3"]


def test_second_download_of_same_track_is_skipped(http, tmp_path, monkeypatch):
    # Настоящая запись тегов: пропуск опирается на ID в тегах файла.
    provider = YandexMusicProvider()
    monkeypatch.setattr(provider, "_download_cover", lambda track, album: None)
    track = make_track(FakeDownloadInfo(192), albums=[make_album()])
    monkeypatch.setattr(provider, "_get_track", lambda url: track)
    url = "https://music.yandex.ru/album/10/track/2"

    first = provider.download(url, tmp_path, DownloadOptions())
    progress = []
    second = provider.download(
        url, tmp_path, DownloadOptions(), progress_callback=progress.append
    )

    assert first is DownloadOutcome.DOWNLOADED
    assert second is DownloadOutcome.SKIPPED
    assert progress == [100.0]
    assert len(http.calls) == 1
    album_dir = tmp_path / "Artist" / "Album (2020)"
    assert [path.name for path in album_dir.iterdir()] == ["03 - Song.mp3"]


def test_different_track_with_same_name_is_not_skipped(http, tmp_path, monkeypatch):
    provider = YandexMusicProvider()
    monkeypatch.setattr(provider, "_download_cover", lambda track, album: None)
    first_track = make_track(FakeDownloadInfo(192), albums=[make_album()])
    second_track = make_track(FakeDownloadInfo(192), albums=[make_album()])
    second_track.id = 3
    tracks = iter([first_track, second_track])
    monkeypatch.setattr(provider, "_get_track", lambda url: next(tracks))

    provider.download(TRACK_URL, tmp_path, DownloadOptions())
    outcome = provider.download(TRACK_URL, tmp_path, DownloadOptions())

    assert outcome is DownloadOutcome.DOWNLOADED
    album_dir = tmp_path / "Artist" / "Album (2020)"
    assert sorted(path.name for path in album_dir.iterdir()) == [
        "03 - Song (2).mp3",
        "03 - Song.mp3",
    ]


class FakeFileInfo:
    """Ответ get-file-info: FileInfo с вложенным FileDownloadInfo."""

    def __init__(self, codec="flac", transport="raw", key=None, url=DIRECT_LINK):
        self.download_info = SimpleNamespace(
            codec=codec,
            transport=transport,
            key=key,
            url=url,
            client=SimpleNamespace(request=SimpleNamespace(proxies=None)),
        )


def make_lossless_track(file_info, calls=None):
    track = make_track(albums=[make_album()])

    def get_file_info(**kwargs):
        if calls is not None:
            calls.append(kwargs)
        return file_info

    track.get_file_info = get_file_info
    return track


def test_lossless_downloads_flac(provider, http, tmp_path, monkeypatch):
    calls = []
    track = make_lossless_track(FakeFileInfo(), calls)
    monkeypatch.setattr(provider, "_get_track", lambda url: track)

    outcome = provider.download(
        TRACK_URL, tmp_path, DownloadOptions(lossless=True)
    )

    flac = tmp_path / "Artist" / "Album (2020)" / "03 - Song.flac"
    assert outcome is DownloadOutcome.DOWNLOADED
    assert flac.read_bytes() == b"".join(CHUNKS)
    assert calls == [
        {
            "quality": "lossless",
            "codecs": ["flac-mp4", "flac", "mp3"],
            "transport": "raw",
        }
    ]
    assert http.calls[0][0] == DIRECT_LINK
    assert [path.name for path in provider.tagged] == ["03 - Song.flac.part"]


def test_lossless_falls_back_to_mp3_when_no_flac(
    provider, http, tmp_path, monkeypatch
):
    track = make_lossless_track(FakeFileInfo(codec="mp3"))
    monkeypatch.setattr(provider, "_get_track", lambda url: track)

    provider.download(TRACK_URL, tmp_path, DownloadOptions(lossless=True))

    album_dir = tmp_path / "Artist" / "Album (2020)"
    assert [path.name for path in album_dir.iterdir()] == ["03 - Song.mp3"]


@pytest.mark.parametrize(
    "file_info",
    [None, FakeFileInfo(url=""), SimpleNamespace(download_info=None)],
)
def test_lossless_without_file_fails(provider, http, tmp_path, monkeypatch, file_info):
    track = make_lossless_track(file_info)
    monkeypatch.setattr(provider, "_get_track", lambda url: track)

    with pytest.raises(RuntimeError, match="lossless"):
        provider.download(TRACK_URL, tmp_path, DownloadOptions(lossless=True))
    assert list(tmp_path.iterdir()) == []


def test_lossless_rejects_unknown_codec(provider, http, tmp_path, monkeypatch):
    track = make_lossless_track(FakeFileInfo(codec="aac-mp4"))
    monkeypatch.setattr(provider, "_get_track", lambda url: track)

    with pytest.raises(RuntimeError, match="aac-mp4"):
        provider.download(TRACK_URL, tmp_path, DownloadOptions(lossless=True))


def test_encrypted_file_is_decrypted_while_streaming(
    provider, http, tmp_path, monkeypatch
):
    class XorDecryptor:
        """Заглушка AES: проверяем, что каждая порция проходит через update."""

        def update(self, chunk):
            return bytes(byte ^ 0xFF for byte in chunk)

        def finalize(self):
            return b"!"

    keys = []

    def fake_make_decryptor(key):
        keys.append(key)
        return XorDecryptor()

    monkeypatch.setattr(
        yandex_music_provider, "_make_decryptor", fake_make_decryptor
    )
    track = make_lossless_track(FakeFileInfo(transport="encraw", key="00ff"))
    monkeypatch.setattr(provider, "_get_track", lambda url: track)

    provider.download(TRACK_URL, tmp_path, DownloadOptions(lossless=True))

    flac = tmp_path / "Artist" / "Album (2020)" / "03 - Song.flac"
    expected = bytes(byte ^ 0xFF for byte in b"".join(CHUNKS)) + b"!"
    assert flac.read_bytes() == expected
    assert keys == ["00ff"]


def test_raw_transport_is_not_decrypted(provider, http, tmp_path, monkeypatch):
    def unexpected(key):
        raise AssertionError("расшифровка не нужна")

    monkeypatch.setattr(yandex_music_provider, "_make_decryptor", unexpected)
    # Ключ есть, но transport=raw — файл не зашифрован.
    track = make_lossless_track(FakeFileInfo(transport="raw", key="00ff"))
    monkeypatch.setattr(provider, "_get_track", lambda url: track)

    provider.download(TRACK_URL, tmp_path, DownloadOptions(lossless=True))


def test_missing_cryptography_gives_clear_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "cryptography", None)
    monkeypatch.setitem(sys.modules, "cryptography.hazmat.primitives.ciphers", None)

    with pytest.raises(RuntimeError, match="uv add cryptography"):
        yandex_music_provider._make_decryptor("00" * 16)


def test_decryptor_matches_library_decryption():
    pytest.importorskip("cryptography")
    from yandex_music.utils.decrypt import decrypt_track

    key = "000102030405060708090a0b0c0d0e0f"
    encrypted = bytes(range(256)) * 300
    decryptor = yandex_music_provider._make_decryptor(key)
    # Порциями, как при скачивании: CTR должен продолжать счётчик.
    streamed = b"".join(
        decryptor.update(encrypted[i : i + 1000])
        for i in range(0, len(encrypted), 1000)
    ) + decryptor.finalize()

    assert streamed == decrypt_track(encrypted, key)


def test_existing_flac_is_skipped_without_api_calls(http, tmp_path, monkeypatch):
    provider = YandexMusicProvider()
    monkeypatch.setattr(provider, "_download_cover", lambda track, album: None)
    calls = []
    track = make_lossless_track(FakeFileInfo(), calls)
    monkeypatch.setattr(provider, "_get_track", lambda url: track)
    album_dir = tmp_path / "Artist" / "Album (2020)"
    album_dir.mkdir(parents=True)
    existing = make_flac(album_dir / "03 - Song.flac")
    write_tags(
        existing, TrackMetadata(source_id="yandex:2", title="Song"), "flac"
    )

    outcome = provider.download(
        TRACK_URL, tmp_path, DownloadOptions(lossless=True)
    )

    assert outcome is DownloadOutcome.SKIPPED
    assert calls == []
    assert http.calls == []


def test_mp3_copy_does_not_block_lossless_download(provider, http, tmp_path, monkeypatch):
    # Раньше скачанный MP3 не мешает скачать FLAC того же трека.
    album_dir = tmp_path / "Artist" / "Album (2020)"
    album_dir.mkdir(parents=True)
    (album_dir / "03 - Song.mp3").write_bytes(b"mp3")
    track = make_lossless_track(FakeFileInfo())
    monkeypatch.setattr(provider, "_get_track", lambda url: track)

    outcome = provider.download(
        TRACK_URL, tmp_path, DownloadOptions(lossless=True)
    )

    assert outcome is DownloadOutcome.DOWNLOADED
    assert (album_dir / "03 - Song.flac").exists()


def test_flac_in_mp4_is_remuxed_to_flac(provider, http, tmp_path, monkeypatch):
    """Яндекс отдаёт lossless как flac-mp4: звук вынимается из MP4 в .flac."""
    remuxed = []

    def fake_remux(source, destination, container):
        remuxed.append((source.name, destination.name, container))
        assert source.read_bytes() == b"".join(CHUNKS)
        destination.write_bytes(b"flac data")

    monkeypatch.setattr(yandex_music_provider, "remux_audio", fake_remux)
    track = make_lossless_track(FakeFileInfo(codec="flac-mp4"))
    monkeypatch.setattr(provider, "_get_track", lambda url: track)

    outcome = provider.download(
        TRACK_URL, tmp_path, DownloadOptions(lossless=True)
    )

    album_dir = tmp_path / "Artist" / "Album (2020)"
    assert outcome is DownloadOutcome.DOWNLOADED
    assert remuxed == [
        ("03 - Song.flac.mp4.part", "03 - Song.flac.part", "flac")
    ]
    # Временные файлы удалены, остался только FLAC.
    assert [path.name for path in album_dir.iterdir()] == ["03 - Song.flac"]
    assert (album_dir / "03 - Song.flac").read_bytes() == b"flac data"
    assert [path.name for path in provider.tagged] == ["03 - Song.flac.part"]


def test_remux_error_removes_temporary_files(provider, http, tmp_path, monkeypatch):
    def broken_remux(source, destination, container):
        destination.write_bytes(b"half")
        raise RuntimeError("Не удалось переупаковать аудио")

    monkeypatch.setattr(yandex_music_provider, "remux_audio", broken_remux)
    track = make_lossless_track(FakeFileInfo(codec="flac-mp4"))
    monkeypatch.setattr(provider, "_get_track", lambda url: track)

    with pytest.raises(RuntimeError, match="переупаковать"):
        provider.download(TRACK_URL, tmp_path, DownloadOptions(lossless=True))

    album_dir = tmp_path / "Artist" / "Album (2020)"
    assert list(album_dir.iterdir()) == []


def test_get_info_returns_artist_separately(monkeypatch):
    provider = YandexMusicProvider()
    track = make_track()
    track.duration_ms = 187000
    track.version = "Live"
    monkeypatch.setattr(provider, "_get_track", lambda url: track)

    info = provider.get_info(TRACK_URL)

    assert info.title == "Song (Live)"
    assert info.artist == "Artist"
    assert info.display_name == "Artist — Song (Live)"
    assert info.duration_seconds == 187
