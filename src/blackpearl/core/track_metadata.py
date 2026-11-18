"""Метаданные трека: раскладка по папкам и ID3-теги.

Модуль не зависит от конкретного источника: провайдер заполняет
TrackMetadata, а дальше путь к файлу и теги строятся одинаково.
"""

from dataclasses import dataclass, field
from pathlib import Path

from typing import Literal

from mutagen import MutagenError
from mutagen.flac import FLAC, Picture
from mutagen.id3 import (
    APIC,
    ID3,
    TALB,
    TCON,
    TDRC,
    TIT2,
    TPE1,
    TPE2,
    TPOS,
    TRCK,
    TXXX,
    ID3NoHeaderError,
)

from blackpearl.core.filenames import sanitize_filename

AudioFormat = Literal["mp3", "flac"]
SUFFIXES: dict[str, str] = {"mp3": ".mp3", "flac": ".flac"}

VARIOUS_ARTISTS = "Various Artists"
# Имя пользовательского тега, в котором хранится ID трека в источнике.
SOURCE_ID_TAG = "BLACKPEARL_SOURCE_ID"
# Папки короче имён файлов: путь «папка/папка/файл» должен
# укладываться в лимит длины пути Windows.
MAX_FOLDER_NAME_LENGTH = 80


@dataclass(frozen=True)
class TrackMetadata:
    # Уникальный ID в источнике, например "yandex:12345".
    source_id: str
    title: str
    artists: list[str] = field(default_factory=list)
    album_title: str | None = None
    album_artist: str | None = None
    year: int | None = None
    genre: str | None = None
    track_number: int | None = None
    disc_number: int | None = None

    @property
    def display_name(self) -> str:
        """«Исполнитель — Название» или просто название."""
        artists = ", ".join(self.artists)
        return f"{artists} — {self.title}" if artists else self.title


def library_location(
    metadata: TrackMetadata,
    output_dir: Path,
    organize_by_album: bool = True,
) -> tuple[Path, str]:
    """Возвращает (папка, имя файла без расширения) для трека.

    С раскладкой по альбомам:
        Исполнитель альбома/Альбом (Год)/01 - Название
    Для многодисковых альбомов номер включает диск: 2-01 - Название.
    Если исполнитель трека отличается от исполнителя альбома
    (сборники, совместные треки), он добавляется в имя файла.

    Без раскладки или без данных об альбоме — плоско:
        Исполнитель — Название
    """
    if not organize_by_album or not metadata.album_title:
        return output_dir, sanitize_filename(metadata.display_name)

    album_artist = metadata.album_artist or VARIOUS_ARTISTS
    album_folder = metadata.album_title
    if metadata.year:
        album_folder = f"{album_folder} ({metadata.year})"

    directory = (
        output_dir
        / sanitize_filename(album_artist, MAX_FOLDER_NAME_LENGTH)
        / sanitize_filename(album_folder, MAX_FOLDER_NAME_LENGTH)
    )

    track_artists = ", ".join(metadata.artists)
    name = (
        metadata.title
        if not track_artists or track_artists == album_artist
        else f"{track_artists} — {metadata.title}"
    )
    if metadata.track_number:
        number = f"{metadata.track_number:02d}"
        if metadata.disc_number and metadata.disc_number > 1:
            number = f"{metadata.disc_number}-{number}"
        name = f"{number} - {name}"

    return directory, sanitize_filename(name)


def read_source_id(path: Path) -> str | None:
    """Читает ID трека из тегов MP3 или FLAC.

    None, если тега нет или файл не читается.
    """
    try:
        if path.suffix.lower() == ".flac":
            values = FLAC(path).get(SOURCE_ID_TAG) or []
        else:
            frames = ID3(path).getall(f"TXXX:{SOURCE_ID_TAG}")
            values = frames[0].text if frames else []
    except (ID3NoHeaderError, MutagenError, OSError):
        return None
    return str(values[0]) if values else None


def resolve_target(
    directory: Path,
    stem: str,
    suffix: str,
    source_id: str,
) -> tuple[Path, bool]:
    """Подбирает путь для сохранения трека.

    Перебирает «stem», «stem (2)», «stem (3)»...:
    - файл с тем же source_id уже есть — возвращает (его путь, True),
      трек скачан ранее и его можно пропустить;
    - встретилось свободное имя — возвращает (путь, False).
    Файлы с тем же именем, но другим треком внутри не перезаписываются.
    """
    number = 1
    while True:
        name = stem if number == 1 else f"{stem} ({number})"
        path = directory / f"{name}{suffix}"
        if not path.exists():
            return path, False
        if read_source_id(path) == source_id:
            return path, True
        number += 1


def write_tags(
    path: Path,
    metadata: TrackMetadata,
    audio_format: AudioFormat,
    cover: tuple[bytes, str] | None = None,
) -> None:
    """Записывает теги в файл указанного формата.

    Формат передаётся явно: во время загрузки файл называется *.part.
    """
    if audio_format == "flac":
        write_flac_tags(path, metadata, cover)
    else:
        write_id3_tags(path, metadata, cover)


def write_flac_tags(
    path: Path,
    metadata: TrackMetadata,
    cover: tuple[bytes, str] | None = None,
) -> None:
    """Записывает Vorbis-комментарии и обложку в FLAC."""
    audio = FLAC(path)

    audio["TITLE"] = metadata.title
    if metadata.artists:
        audio["ARTIST"] = metadata.artists
    if metadata.album_title:
        audio["ALBUM"] = metadata.album_title
    if metadata.album_artist:
        audio["ALBUMARTIST"] = metadata.album_artist
    if metadata.year:
        audio["DATE"] = str(metadata.year)
    if metadata.genre:
        audio["GENRE"] = metadata.genre
    if metadata.track_number:
        audio["TRACKNUMBER"] = str(metadata.track_number)
    if metadata.disc_number:
        audio["DISCNUMBER"] = str(metadata.disc_number)
    audio[SOURCE_ID_TAG] = metadata.source_id

    if cover is not None:
        data, mime = cover
        picture = Picture()
        picture.type = 3  # обложка (front cover)
        picture.mime = mime
        picture.desc = "Cover"
        picture.data = data
        audio.clear_pictures()
        audio.add_picture(picture)

    audio.save()


def write_id3_tags(
    path: Path,
    metadata: TrackMetadata,
    cover: tuple[bytes, str] | None = None,
) -> None:
    """Записывает ID3v2.3-теги в MP3. cover — (данные, MIME-тип)."""
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()

    tags.add(TIT2(encoding=3, text=metadata.title))
    if metadata.artists:
        tags.add(TPE1(encoding=3, text=metadata.artists))
    if metadata.album_title:
        tags.add(TALB(encoding=3, text=metadata.album_title))
    if metadata.album_artist:
        tags.add(TPE2(encoding=3, text=metadata.album_artist))
    if metadata.year:
        tags.add(TDRC(encoding=3, text=str(metadata.year)))
    if metadata.genre:
        tags.add(TCON(encoding=3, text=metadata.genre))
    if metadata.track_number:
        tags.add(TRCK(encoding=3, text=str(metadata.track_number)))
    if metadata.disc_number:
        tags.add(TPOS(encoding=3, text=str(metadata.disc_number)))
    tags.add(TXXX(encoding=3, desc=SOURCE_ID_TAG, text=metadata.source_id))

    if cover is not None:
        data, mime = cover
        tags.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=data))

    tags.update_to_v23()
    tags.save(path, v2_version=3)
