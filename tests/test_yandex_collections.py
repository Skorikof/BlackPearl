from types import SimpleNamespace

import pytest

from blackpearl.providers.yandex_music_provider import YandexMusicProvider

PLAYLIST_UUID = "cb9410fe-a6c0-7d9d-86b4-7e9b27870f3d"


def make_track(track_id, album_id):
    return SimpleNamespace(
        id=track_id,
        title=f"Track {track_id}",
        artists=[SimpleNamespace(name="Artist")],
        albums=[SimpleNamespace(id=album_id)],
        duration_ms=180000,
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://music.yandex.ru/album/123",
        "https://music.yandex.ru/album/123/",
        "https://music.yandex.ru/album/123?utm_source=share",
        "https://music.yandex.ru/users/someone/playlists/3",
        f"https://music.yandex.ru/playlists/{PLAYLIST_UUID}",
        f"https://music.yandex.ru/playlists/lk.{PLAYLIST_UUID}",
        "https://music.yandex.ru/artist/160247/tracks",
        "https://music.yandex.ru/artist/160247/tracks/",
    ],
)
def test_is_collection_true_for_collections(url):
    assert YandexMusicProvider().is_collection(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://music.yandex.ru/album/123/track/456",
        "https://music.yandex.ru/album/123/track/456/",
        "https://music.yandex.ru/track/456",
        "https://music.yandex.ru/artist/160247",
    ],
)
def test_is_collection_false_for_tracks(url):
    assert not YandexMusicProvider().is_collection(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://music.yandex.ru/album/123",
        "https://music.yandex.ru/album/123/",
    ],
)
def test_album_with_trailing_slash_is_loaded(monkeypatch, url):
    provider = YandexMusicProvider()

    class FakeClient:
        def albums_with_tracks(self, album_id):
            assert album_id == "123"
            return SimpleNamespace(
                volumes=[
                    [make_track(1, 123), make_track(2, 123)],
                    [make_track(3, 123)],
                ]
            )

    monkeypatch.setattr(provider, "_get_client", lambda: FakeClient())
    tracks = provider.get_collection_tracks(url)

    assert [track.track_id for track in tracks] == ["1", "2", "3"]


def test_uuid_playlist_uses_tracks_returned_by_fetch_tracks(monkeypatch):
    """Playlist.fetch_tracks() возвращает треки, но не сохраняет их
    в playlist.tracks — провайдер должен использовать возвращённое значение."""
    provider = YandexMusicProvider()

    class FakePlaylist:
        tracks = None

        def fetch_tracks(self):
            return [make_track(1, 10), make_track(2, 20)]

    class FakeClient:
        def playlist(self, playlist_uuid):
            assert playlist_uuid == PLAYLIST_UUID
            return FakePlaylist()

    monkeypatch.setattr(provider, "_get_client", lambda: FakeClient())
    tracks = provider.get_collection_tracks(
        f"https://music.yandex.ru/playlists/{PLAYLIST_UUID}"
    )

    assert [track.track_id for track in tracks] == ["1", "2"]
    assert [track.album_id for track in tracks] == ["10", "20"]


def test_uuid_playlist_with_tracks_does_not_refetch(monkeypatch):
    provider = YandexMusicProvider()

    class FakePlaylist:
        tracks = [make_track(7, 70)]

        def fetch_tracks(self):
            raise AssertionError("fetch_tracks не должен вызываться")

    class FakeClient:
        def playlist(self, playlist_uuid):
            return FakePlaylist()

    monkeypatch.setattr(provider, "_get_client", lambda: FakeClient())
    tracks = provider.get_collection_tracks(
        f"https://music.yandex.ru/playlists/{PLAYLIST_UUID}"
    )

    assert [track.track_id for track in tracks] == ["7"]
