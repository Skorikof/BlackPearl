from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MediaInfo:
    title: str
    url: str
    media_type: str
    duration_seconds: float | None = None
    

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
    def download(self, url: str, output_path: Path) -> None:
        """Скачивает медиа по данному URL в указанный путь."""
        ...
