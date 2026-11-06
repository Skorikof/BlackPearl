import re
from io import BytesIO
from pathlib import Path
from threading import Event
from urllib.parse import urlparse

from mutagen.id3 import (
    APIC,
    ID3,
    TALB,
    TDRC,
    TIT2,
    TPE1,
    ID3NoHeaderError,
)
from PIL import Image
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
        """Извлекает ID трека и альбома из URL."""
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
        """Создаёт и возвращает экземпляр клиента Yandex Music."""
        if not settings.yandex_music_token:
            raise RuntimeError(
                "Не задан YANDEX_MUSIC_TOKEN"
            )
        return Client(settings.yandex_music_token).init()

    def _get_track(self, url: str):
        """Получает объект трека по URL."""
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
        """Получает информацию о треке по URL."""
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
        
    def _select_bitrate(self, track, requested_bitrate: int) -> int:
        download_info = track.get_download_info()
        if not download_info:
            raise RuntimeError(
                "Яндекс Музыка не вернула варианты загрузки"
            )
        available = sorted({
            item.bitrate_in_kbps
            for item in download_info
            if item.codec == "mp3"
            and not item.preview
            and item.bitrate_in_kbps
        })
        if not available:
            raise RuntimeError(
                "Для трека нет доступных вариантов MP3"
            )
        # Выбираем максимальный доступный битрейт,
        # который не превышает заданный пользователем.
        suitable = [
            bitrate
            for bitrate in available
            if bitrate <= requested_bitrate
        ]
        if suitable:
            return max(suitable)
        # Если вариантов ниже заданного нет,
        # используем самый низкий доступный.
        return min(available)
        
    def _write_metadata(self, track, output_path: Path) -> None:
        """Запись метаданных в MP3-файл."""
        try:
            tags = ID3(output_path)
        except ID3NoHeaderError:
            tags = ID3()
        tags.add(TIT2(encoding=3, text=track.title or "Без названия"))
        artists = [
            artist.name
            for artist in (track.artists or [])
            if artist.name
        ]
        if artists:
            tags.add(TPE1(encoding=3, text=artists))
        albums = track.albums or []
        if albums:
            album = albums[0]
            if album.title:
                tags.add(TALB(encoding=3, text=album.title))
            if album.year:
                tags.add(TDRC(encoding=3, text=str(album.year)))

        # Загружаем обложку и добавляем её в MP3.
        cover = None
        # Сначала пробуем получить обложку самого трека.
        if track.cover_uri:
            cover = track.download_cover_bytes(size="400x400")

        # Если у трека обложки нет — берём её из альбома.
        if not cover and track.albums:
            album = track.albums[0]
            if album.cover_uri:
                cover = album.download_cover_bytes(size="400x400")

        if cover:
            try:
                image = Image.open(BytesIO(cover))
                image.verify()
                image_format = image.format
                mime_types = {
                    "JPEG": "image/jpeg",
                    "PNG": "image/png",
                }
                mime = mime_types.get(image_format)
                if mime is None:
                    raise ValueError(
                        f"Неподдерживаемый формат обложки: {image_format}"
                    )
                tags.add(
                    APIC(
                        encoding=3,
                        mime=mime,
                        type=3,
                        desc="Cover",
                        data=cover,
                    )
                )
                print(
                    f"Обложка добавлена: {image_format}, "
                    f"{len(cover)} байт"
                )
            except Exception as error:
                print(f"Ошибка обработки обложки: {error}")
            
        tags.update_to_v23()
        tags.save(output_path, v2_version=3)

    def download(
        self,
        url: str,
        output_dir: Path,
        audio_bitrate_kbps: int | None = None,
        progress_callback=None,
        cancel_event: Event | None = None,
        ) -> None:
        """Скачивает трек по URL в указанный каталог."""
        output_dir.mkdir(parents=True, exist_ok=True)
        if cancel_event is not None and cancel_event.is_set():
            return
        track = self._get_track(url)
        artists = ", ".join(
            artist.name
            for artist in (track.artists or [])
            if artist.name
        )
        title = track.title or "Без названия"
        filename = f"{artists} — {title}" if artists else title
        filename = re.sub(
            r'[<>:"/\\|?*\x00-\x1f]',
            "_",
            filename,
        )
        output_path = output_dir / f"{filename}.mp3"
        # Загружаем аудио в выбранном качестве.
        
        requested_bitrate = audio_bitrate_kbps or 192
        actual_bitrate = self._select_bitrate(
            track,
            requested_bitrate,
        )

        print(
            f"Выбран битрейт: {actual_bitrate} кбит/с "
            f"(запрошено {requested_bitrate})"
        )

        track.download(
            str(output_path),
            codec="mp3",
            bitrate_in_kbps=actual_bitrate,
        )
        
        
        if cancel_event is not None and cancel_event.is_set():
            output_path.unlink(missing_ok=True)
            return
        self._write_metadata(track, output_path)
        if progress_callback is not None:
            progress_callback(100.0)
