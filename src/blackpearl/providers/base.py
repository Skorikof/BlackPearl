from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import ClassVar, Literal

MediaKind = Literal["audio", "video"]


@dataclass(frozen=True)
class DownloadOptions:
    """Что и в каком качестве скачивать."""

    kind: MediaKind = "audio"
    audio_bitrate_kbps: int = 192
    # Максимальная высота видео (1080, 720...); None — без ограничения.
    video_max_height: int | None = None


@dataclass
class MediaInfo:
    title: str
    url: str
    media_type: str
    duration_seconds: float | None = None


@dataclass
class TrackEntry:
    track_id: str
    album_id: str
    title: str
    artists: str
    duration_seconds: float | None
    url: str


ProgressCallback = Callable[[float], None]


class MediaProvider(ABC):
    """Базовый интерфейс источника медиа."""

    # Какие режимы скачивания поддерживает источник.
    supported_kinds: ClassVar[frozenset[MediaKind]] = frozenset({"audio", "video"})

    def supports(self, kind: MediaKind) -> bool:
        return kind in self.supported_kinds

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """Проверяет, может ли источник обработать данный URL."""
        ...
        
    @abstractmethod
    def get_info(self, url: str) -> MediaInfo:
        """Возвращает информацию о медиа по данному URL."""
        ...
        
    @abstractmethod
    def download(
        self,
        url: str,
        output_dir: Path,
        options: DownloadOptions,
        progress_callback: ProgressCallback | None = None,
        cancel_event: Event | None = None,
        ) -> None:
        """Скачивает медиа по данному URL в указанный путь."""
        ...
