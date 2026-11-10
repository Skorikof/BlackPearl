from types import SimpleNamespace

from blackpearl.providers.yandex_music_provider import YandexMusicProvider


def test_provider_accepts_artist_tracks_url():
    provider = YandexMusicProvider()
    assert provider.can_handle("https://music.yandex.ru/artist/160247/tracks")


def test_provider_rejects_artist_root_url():
    provider = YandexMusicProvider()
    assert not provider.can_handle("https://music.yandex.ru/artist/160247")


def test_provider_loads_all_artist_track_pages(monkeypatch):
    provider = YandexMusicProvider()

    def make_track(track_id, album_id):
        return SimpleNamespace(
            id=track_id,
            title=f"Track {track_id}",
            artists=[SimpleNamespace(name="Artist")],
            albums=[SimpleNamespace(id=album_id)],
            duration_ms=180000,
        )

    pages = {
        0: SimpleNamespace(
            tracks=[make_track(1, 10), make_track(2, 20)],
            pager=SimpleNamespace(page=0, per_page=2, total=3),
        ),
        1: SimpleNamespace(
            tracks=[make_track(3, 30)],
            pager=SimpleNamespace(page=1, per_page=2, total=3),
        ),
    }

    class FakeClient:
        def artists_tracks(self, artist_id, page=0, page_size=20):
            assert artist_id == "160247"
            return pages[page]

    monkeypatch.setattr(provider, "_get_client", lambda: FakeClient())
    tracks = provider.get_collection_tracks(
        "https://music.yandex.ru/artist/160247/tracks"
    )

    assert [track.track_id for track in tracks] == ["1", "2", "3"]
    assert [track.album_id for track in tracks] == ["10", "20", "30"]
