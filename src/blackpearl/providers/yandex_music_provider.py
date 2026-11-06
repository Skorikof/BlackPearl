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
from blackpearl.providers.base import MediaInfo, MediaProvider, TrackEntry


class YandexMusicProvider(MediaProvider):
    """Провайдер для работы с Яндекс Музыкой."""
    TRACK_PATTERN = re.compile(r"/track/(\d+)")
    ALBUM_PATTERN = re.compile(r"/album/(\d+)")
    PLAYLIST_PATTERN = re.compile(r"/users/([^/]+)/playlists/(\d+)")
    PLAYLIST_UUID_PATTERN = re.compile(r"/playlists/((?:lk\.)?[0-9a-fA-F]{8}-"
                                    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                                    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
                                    )

    def can_handle(self, url: str) -> bool:
        parsed = urlparse(url)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname not in {
                "music.yandex.ru",
                "music.yandex.com",
                "music.yandex.by",
                "music.yandex.kz",
            }
        ):
            return False
        path = parsed.path
        return any(
            pattern.search(path)
            for pattern in (
                self.TRACK_PATTERN,
                self.ALBUM_PATTERN,
                self.PLAYLIST_PATTERN,
                self.PLAYLIST_UUID_PATTERN,
            )
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
        
    def _make_track_entry(self, item) -> TrackEntry | None:
        """Преобразует объект библиотеки в элемент нашей коллекции."""
        track = getattr(item, "track", None) or item
        # TrackShort может содержать только краткую информацию.
        if not getattr(track, "title", None):
            fetch_track = getattr(item, "fetch_track", None)
            if fetch_track is not None:
                track = fetch_track()
        track_id = getattr(track, "id", None)
        albums = getattr(track, "albums", None) or []
        album_id = (
            albums[0].id
            if albums
            else getattr(item, "album_id", None)
        )
        if track_id is None or album_id is None:
            return None
        artists = ", ".join(
            artist.name
            for artist in (getattr(track, "artists", None) or [])
            if artist.name
        )
        duration_ms = getattr(track, "duration_ms", None)
        return TrackEntry(
            track_id=str(track_id),
            album_id=str(album_id),
            title=getattr(track, "title", None) or "Без названия",
            artists=artists,
            duration_seconds=(
                duration_ms / 1000
                if duration_ms
                else None
            ),
            url=(
                f"https://music.yandex.ru/album/{album_id}"
                f"/track/{track_id}"
            ),
        )

    def get_collection_tracks(self, url: str) -> list[TrackEntry]:
        """Получает список треков из альбома или плейлиста."""
        parsed = urlparse(url)
        client = self._get_client()
        album_match = self.ALBUM_PATTERN.search(parsed.path)
        playlist_uuid_match = self.PLAYLIST_UUID_PATTERN.search(urlparse(url).path)
        playlist_match = self.PLAYLIST_PATTERN.search(parsed.path)
        raw_tracks = []
        if album_match:
            album_id = album_match.group(1)
            album = client.albums_with_tracks(album_id)
            if album is None or not album.volumes:
                raise RuntimeError("Не удалось получить альбом")
            # В альбоме может быть несколько дисков.
            for volume in album.volumes:
                raw_tracks.extend(volume)
                
        elif playlist_uuid_match:
            playlist_uuid = playlist_uuid_match.group(1)
            playlist = client.playlist(playlist_uuid)
            if playlist is None:
                raise ValueError("Не удалось получить плейлист по UUID")
            if playlist.tracks is None:
                playlist.fetch_tracks()
            raw_tracks = playlist.tracks or []
        
        elif playlist_match:
            user_id, playlist_id = playlist_match.groups()
            playlist = client.users_playlists(
                kind=playlist_id,
                user_id=user_id,
            )
            raw_tracks = playlist.tracks or []
        else:
            raise ValueError(
                "Ссылка не является альбомом или плейлистом"
            )
        entries = []
        for item in raw_tracks:
            entry = self._make_track_entry(item)
            if entry is not None:
                entries.append(entry)
        if not entries:
            raise RuntimeError(
                "В коллекции не найдено доступных треков"
            )
        return entries

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
