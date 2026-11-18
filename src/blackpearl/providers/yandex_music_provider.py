import re
from io import BytesIO
from pathlib import Path
from threading import Event, Lock
from urllib.parse import urlparse

import logging

import requests
from PIL import Image
from yandex_music import Client

from blackpearl.core.config import settings
from blackpearl.core.track_metadata import (
    VARIOUS_ARTISTS,
    TrackMetadata,
    library_location,
    resolve_target,
    write_id3_tags,
)
from blackpearl.providers.base import (
    CollectionProvider,
    DownloadCancelled,
    DownloadOptions,
    DownloadOutcome,
    MediaInfo,
    MediaProvider,
    ProgressCallback,
    TrackEntry,
)


logger = logging.getLogger(__name__)

COVER_SIZE = "400x400"
COVER_MIME_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png"}


def _artist_names(artists) -> list[str]:
    return [artist.name for artist in (artists or []) if artist.name]


def _with_version(title: str, version: str | None) -> str:
    """«Song» + «Remastered 2011» → «Song (Remastered 2011)»."""
    return f"{title} ({version})" if version else title


def _raise_if_cancelled(cancel_event: Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise DownloadCancelled("Загрузка отменена пользователем")


class YandexMusicProvider(MediaProvider, CollectionProvider):
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

    @staticmethod
    def _choose_album(track, album_id: str | None):
        """Альбом, из которого скачивается трек.

        Один трек может входить в несколько альбомов (оригинал, сборник,
        переиздание); берём тот, что указан в ссылке, иначе первый.
        """
        albums = track.albums or []
        if album_id is not None:
            for album in albums:
                if str(album.id) == album_id:
                    return album
        return albums[0] if albums else None

    @staticmethod
    def _build_metadata(track, album) -> TrackMetadata:
        title = _with_version(track.title or "Без названия", track.version)
        artists = _artist_names(track.artists)
        if album is None:
            return TrackMetadata(
                source_id=f"yandex:{track.id}",
                title=title,
                artists=artists,
            )

        album_artists = _artist_names(album.artists)
        is_compilation = album.type == "compilation" or any(
            getattr(artist, "various", False) for artist in (album.artists or [])
        )
        position = album.track_position
        return TrackMetadata(
            source_id=f"yandex:{track.id}",
            title=title,
            artists=artists,
            album_title=_with_version(album.title, album.version)
            if album.title
            else None,
            album_artist=(
                VARIOUS_ARTISTS
                if is_compilation or not album_artists
                else ", ".join(album_artists)
            ),
            year=album.year or album.original_release_year,
            genre=album.genre,
            track_number=position.index if position is not None else None,
            disc_number=position.volume if position is not None else None,
        )

    @staticmethod
    def _download_cover(track, album) -> tuple[bytes, str] | None:
        """Обложка трека (или альбома) и её MIME-тип; None, если её нет."""
        try:
            data = None
            if track.cover_uri:
                data = track.download_cover_bytes(size=COVER_SIZE)
            if not data and album is not None and album.cover_uri:
                data = album.download_cover_bytes(size=COVER_SIZE)
            if not data:
                return None

            image = Image.open(BytesIO(data))
            image.verify()
            mime = COVER_MIME_TYPES.get(image.format)
            if mime is None:
                raise ValueError(
                    f"Неподдерживаемый формат обложки: {image.format}"
                )
            return data, mime
        except Exception as error:
            # Без обложки трек всё равно полезен — не роняем загрузку.
            logger.warning("Не удалось получить обложку: %s", error)
            return None

    def _write_metadata(
        self, track, album, metadata: TrackMetadata, path: Path
    ) -> None:
        """Запись ID3-тегов и обложки в MP3-файл."""
        write_id3_tags(path, metadata, self._download_cover(track, album))

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
        ) -> DownloadOutcome:
        """Скачивает трек по URL в указанный каталог.

        Если этот же трек уже лежит в целевой папке (узнаём по ID
        в тегах), повторно не скачивает и возвращает SKIPPED.
        """
        if not self.supports(options.kind):
            raise ValueError("Яндекс Музыка поддерживает только аудио")
        _raise_if_cancelled(cancel_event)
        track = self._get_track(url)
        _, album_id = self._get_track_id(url)
        album = self._choose_album(track, album_id)
        metadata = self._build_metadata(track, album)

        directory, stem = library_location(
            metadata, output_dir, options.organize_by_album
        )
        output_path, already_downloaded = resolve_target(
            directory, stem, ".mp3", metadata.source_id
        )
        if already_downloaded:
            if progress_callback is not None:
                progress_callback(100.0)
            return DownloadOutcome.SKIPPED

        directory.mkdir(parents=True, exist_ok=True)
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
            self._write_metadata(track, album, metadata, part_path)
            part_path.replace(output_path)
        finally:
            part_path.unlink(missing_ok=True)

        if progress_callback is not None:
            progress_callback(100.0)
        return DownloadOutcome.DOWNLOADED
