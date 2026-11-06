from blackpearl.providers.yandex_music_provider import YandexMusicProvider


def test_provider_accepts_yandex_track_url():
    provider = YandexMusicProvider()
    assert provider.can_handle(
        "https://music.yandex.ru/album/123/track/456"
    )


def test_provider_rejects_youtube_url():
    provider = YandexMusicProvider()
    assert not provider.can_handle(
        "https://youtube.com/watch?v=123"
    )


def test_provider_rejects_playlist_url():
    provider = YandexMusicProvider()
    assert not provider.can_handle(
        "https://music.yandex.ru/users/user/playlists/123"
    )


def test_provider_extracts_track_and_album_ids():
    provider = YandexMusicProvider()
    track_id, album_id = provider._get_track_id(
        "https://music.yandex.ru/album/123/track/456"
    )
    assert track_id == "456"
    assert album_id == "123"


def test_provider_extracts_track_id_without_album():
    provider = YandexMusicProvider()
    track_id, album_id = provider._get_track_id(
        "https://music.yandex.ru/track/456"
    )
    assert track_id == "456"
    assert album_id is None
