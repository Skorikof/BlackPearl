from pathlib import Path

import pytest

from blackpearl.providers.base import MediaInfo, MediaProvider


class DemoProvider(MediaProvider):
    """Тестовый провайдер для проверки базового интерфейса MediaProvider."""
    def can_handle(self, url: str) -> bool:
        return "example.com" in url

    def get_info(self, url: str) -> MediaInfo:
        return MediaInfo(
            title="Test video",
            url=url,
            media_type="video",
            duration_seconds=120.0
        )

    def download(self, url: str, output_path: Path) -> None:
        pass


def test_provider_can_handle_url():
    provider = DemoProvider()
    
    assert provider.can_handle("https://example.com/video")
    assert not provider.can_handle("https://other.com/video")
    

def test_provider_get_info():
    provider = DemoProvider()
    
    info = provider.get_info("https://example.com/video")
    
    assert info.title == "Test video"
    assert info.media_type == "video"
    assert info.duration_seconds == 120.0
    

def test_abstract_provider_cannot_be_created():
    with pytest.raises(TypeError):
        MediaProvider()  # Попытка создать экземпляр абстрактного класса должна вызвать ошибку
