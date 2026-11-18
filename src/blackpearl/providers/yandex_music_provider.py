import re
from io import BytesIO
from pathlib import Path
from threading import Event, Lock
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
import requests
from PIL import Image
from yandex_music import Client

from blackpearl.core.config import settings
from blackpearl.core.filenames import sanitize_filename, unique_path
from blackpearl.providers.base import (
    DownloadCancelled,
    DownloadOptions,
    MediaInfo,
    MediaProvider,
    ProgressCallback,
    TrackEntry,
)


def _raise_if_cancelled(cancel_event: Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise DownloadCancelled("Загрузка отменена пользователем")


class YandexMusicProvider(MediaProvider):
    """Провайдер для работы с Яндекс Музыкой."""
    supported_kinds = frozenset({"audio"})
    CHUNK_SIZE = 64 * 1024
    # (подключение, ожидание очередной порции данных), секунды.
    HTTP_TIMEOUT = (10, 30)

    def __init__(self) -> None:
        self._client: Client | None = None
        self._client_token: str | None = None
        self._client_lock = Lock()

    TRACK_PATTERN = re.compile(r"/track/(\d+)")
    ALBUM_PATTERN = re.compile(r"/album/(\d+)")
    # Ссылка на сам альбом (без трека), допускается слэш в конце.
    ALBUM_ONLY_PATTERN = re.compile(r"^/album/(\d+)/?$")
    PLAYLIST_PATTERN = re.compile(r"/users/([^/]+)/playlists/(\d+)")
    PLAYLIST_UUID_PATTERN = re.compile(r"/playlists/((?:lk\.)?[0-9a-fA-F]{8}-"
                                    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                                    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
                                    )
    ARTIST_TRACKS_PATTERN = re.compile(r"^/artist/(\d+)/tracks/?$")

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
                self.ARTIST_TRACKS_PATTERN,
            )
        )

    def is_collection(self, url: str) -> bool:
        """Проверяет, ведёт ли URL на коллекцию (альбом, плейлист,
        треки артиста), а не на отдельный трек."""
        path = urlparse(url).path
        if self.TRACK_PATTERN.search(path):
            return False
        return any(
            pattern.search(path)
            for pattern in (
                self.ALBUM_ONLY_PATTERN,
                self.PLAYLIST_PATTERN,
                self.PLAYLIST_UUID_PATTERN,
                self.ARTIST_TRACKS_PATTERN,
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
        """Возвращает клиент Yandex Music, создавая его при первом обращении.

        Client.init() — отдельный сетевой запрос, поэтому клиент
        создаётся один раз и переиспользуется. Провайдер вызывается
        из разных фоновых потоков, поэтому создание защищено блокировкой.
        """
        token = settings.yandex_music_token
        if not token:
            raise RuntimeError(
                "Не задан YANDEX_MUSIC_TOKEN"
            )
        with self._client_lock:
            if self._client is None or self._client_token != token:
                self._client = Client(token).init()
                self._client_token = token
            return self._client

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
        
    def _select_download_info(self, track, requested_bitrate: int):
        """Выбирает вариант загрузки MP3 (объект DownloadInfo)."""
        download_info = track.get_download_info()
        if not download_info:
            raise RuntimeError(
                "Яндекс Музыка не вернула варианты загрузки"
            )
        available = [
            item
            for item in download_info
            if item.codec == "mp3"
            and not item.preview
            and item.bitrate_in_kbps
        ]
        if not available:
            raise RuntimeError(
                "Для трека нет доступных вариантов MP3"
            )
        # Выбираем максимальный доступный битрейт,
        # который не превышает заданный пользователем.
        suitable = [
            item
            for item in available
            if item.bitrate_in_kbps <= requested_bitrate
        ]
        if suitable:
            return max(suitable, key=lambda item: item.bitrate_in_kbps)
        # Если вариантов ниже заданного нет,
        # используем самый низкий доступный.
        return min(available, key=lambda item: item.bitrate_in_kbps)

    def _stream_to_file(
        self,
        direct_link: str,
        output_path: Path,
        proxies: dict | None,
        progress_callback: ProgressCallback | None,
        cancel_event: Event | None,
    ) -> None:
        """Скачивает файл по прямой ссылке порциями.

        Библиотека yandex-music скачивает файл целиком одним запросом,
        без прогресса и возможности отмены, поэтому сам файл
        загружаем сами. При отмене бросает DownloadCancelled.
        """
        with requests.get(
            direct_link,
            stream=True,
            timeout=self.HTTP_TIMEOUT,
            proxies=proxies,
        ) as response:
            response.raise_for_status()
            try:
                total = int(response.headers.get("Content-Length") or 0)
            except ValueError:
                total = 0
            downloaded = 0

            with output_path.open("wb") as file:
                for chunk in response.iter_content(self.CHUNK_SIZE):
                    _raise_if_cancelled(cancel_event)
                    file.write(chunk)
                    downloaded += len(chunk)
                    if total and progress_callback is not None:
                        progress_callback(min(downloaded / total * 100, 100.0))

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
        """Получает список треков из альбома, плейлиста или страницы артиста."""
        parsed = urlparse(url)
        client = self._get_client()
        album_match = self.ALBUM_ONLY_PATTERN.fullmatch(parsed.path)
        artist_match = self.ARTIST_TRACKS_PATTERN.fullmatch(parsed.path)
        playlist_uuid_match = self.PLAYLIST_UUID_PATTERN.search(parsed.path)
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

        elif artist_match:
            artist_id = artist_match.group(1)
            page = 0
            page_size = 100

            # API возвращает треки исполнителя постранично.
            while True:
                artist_page = client.artists_tracks(
                    artist_id,
                    page=page,
                    page_size=page_size,
                )
                if artist_page is None:
                    break

                page_tracks = artist_page.tracks or []
                raw_tracks.extend(page_tracks)
                if not page_tracks:
                    break

                pager = getattr(artist_page, "pager", None)
                total = getattr(pager, "total", None) if pager is not None else None
                if total is not None:
                    current_page = getattr(pager, "page", page)
                    per_page = getattr(pager, "per_page", page_size) or page_size
                    if (current_page + 1) * per_page >= total:
                        break
                    next_page = current_page + 1
                    if next_page <= page:
                        raise RuntimeError(
                            "Некорректная пагинация треков исполнителя"
                        )
                    page = next_page
                else:
                    # Запасной вариант, если API не вернул пагинатор.
                    if len(page_tracks) < page_size:
                        break
                    page += 1

        elif playlist_uuid_match:
            playlist_uuid = playlist_uuid_match.group(1)
            playlist = client.playlist(playlist_uuid)
            if playlist is None:
                raise ValueError("Не удалось получить плейлист по UUID")
            raw_tracks = playlist.tracks
            if raw_tracks is None:
                # fetch_tracks() возвращает список треков,
                # но не сохраняет его в playlist.tracks.
                raw_tracks = playlist.fetch_tracks()
            raw_tracks = raw_tracks or []

        elif playlist_match:
            user_id, playlist_id = playlist_match.groups()
            playlist = client.users_playlists(
                kind=playlist_id,
                user_id=user_id,
            )
            raw_tracks = playlist.tracks or []
        else:
            raise ValueError(
                "Ссылка не является альбомом, плейлистом или страницей треков артиста"
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
        options: DownloadOptions,
        progress_callback: ProgressCallback | None = None,
        cancel_event: Event | None = None,
        ) -> None:
        """Скачивает трек по URL в указанный каталог."""
        if not self.supports(options.kind):
            raise ValueError("Яндекс Музыка поддерживает только аудио")
        output_dir.mkdir(parents=True, exist_ok=True)
        _raise_if_cancelled(cancel_event)
        track = self._get_track(url)
        artists = ", ".join(
            artist.name
            for artist in (track.artists or [])
            if artist.name
        )
        title = track.title or "Без названия"
        filename = sanitize_filename(
            f"{artists} — {title}" if artists else title
        )
        output_path = unique_path(output_dir, filename, ".mp3")
        # Пока файл не скачан и не размечен тегами, он лежит
        # под временным именем — недокачанных .mp3 не остаётся.
        part_path = output_path.with_name(output_path.name + ".part")

        download_info = self._select_download_info(
            track,
            options.audio_bitrate_kbps,
        )
        _raise_if_cancelled(cancel_event)
        # Прямая ссылка действует около минуты — получаем её
        # непосредственно перед загрузкой.
        direct_link = download_info.get_direct_link()
        proxies = getattr(
            getattr(download_info.client, "request", None), "proxies", None
        )

        try:
            self._stream_to_file(
                direct_link,
                part_path,
                proxies,
                progress_callback,
                cancel_event,
            )
            self._write_metadata(track, part_path)
            part_path.replace(output_path)
        finally:
            part_path.unlink(missing_ok=True)

        if progress_callback is not None:
            progress_callback(100.0)
