from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Event


@dataclass
class MediaInfo:
    title: str
    url: str
    media_type: str
    duration_seconds: float | None = None


ProgressCallback = Callable[[float], None]


class MediaProvider(ABC):
    """Базовый интерфейс источника медиа."""
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
        progress_callback: ProgressCallback | None = None,
        cancel_event: Event | None = None,
        ) -> None:
        """Скачивает медиа по данному URL в указанный путь."""
        ...
