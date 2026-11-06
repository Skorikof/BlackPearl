import re
from pathlib import Path
from threading import Event
from urllib.parse import urlparse

from yandex_music import Client

from blackpearl.core.config import settings
from blackpearl.providers.base import MediaInfo, MediaProvider


class YandexMusicProvider(MediaProvider):
    """Провайдер для работы с Яндекс Музыкой."""

    TRACK_PATTERN = re.compile(r"/track/(\d+)")

    ALBUM_PATTERN = re.compile(r"/album/(\d+)")

    def can_handle(self, url: str) -> bool:
        parsed = urlparse(url)

        return (
            parsed.scheme in {"http", "https"}
            and parsed.hostname is not None
            and parsed.hostname.startswith("music.yandex.")
            and self.TRACK_PATTERN.search(parsed.path) is not None
        )

    def _get_track_id(self, url: str) -> tuple[str, str | None]:
        parsed = urlparse(url)

        track_match = self.TRACK_PATTERN.search(parsed.path)
        album_match = self.ALBUM_PATTERN.search(parsed.path)

        if track_match is None:
            raise ValueError("Не удалось определить ID трека")

        track_id = track_match.group(1)
        album_id = (
            album_match.group(1)
            if album_match is not None
            else None
        )

        return track_id, album_id

    def _get_client(self) -> Client:
        if not settings.yandex_music_token:
            raise RuntimeError(
                "Не задан YANDEX_MUSIC_TOKEN"
            )

        return Client(settings.yandex_music_token).init()

    def _get_track(self, url: str):
        track_id, album_id = self._get_track_id(url)

        client = self._get_client()

        api_track_id = (
            f"{track_id}:{album_id}"
            if album_id
            else track_id
        )

        tracks = client.tracks([api_track_id])

        if not tracks:
            raise RuntimeError("Трек не найден")

        return tracks[0]

    def get_info(self, url: str) -> MediaInfo:
        track = self._get_track(url)

        artists = ", ".join(
            artist.name for artist in (track.artists or [])
        )

        title = track.title or "Без названия"

        if artists:
            title = f"{artists} — {title}"

        duration = (
            track.duration_ms / 1000
            if track.duration_ms
            else None
        )

        return MediaInfo(
            title=title,
            url=url,
            media_type="audio",
            duration_seconds=duration,
        )

    def download(
        self,
        url: str,
        output_dir: Path,
        progress_callback=None,
        cancel_event: Event | None = None,
    ) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)

        if cancel_event is not None and cancel_event.is_set():
            return

        track = self._get_track(url)

        artists = ", ".join(
            artist.name for artist in (track.artists or [])
        )

        title = track.title or "Без названия"

        filename = (
            f"{artists} - {title}"
            if artists
            else title
        )

        # Убираем символы, запрещённые в именах файлов Windows.
        filename = re.sub(
            r'[<>:"/\\|?*\x00-\x1f]',
            "_",
            filename,
        )

        output_path = output_dir / f"{filename}.mp3"

        track.download(str(output_path))

        if progress_callback is not None:
            progress_callback(100.0)
