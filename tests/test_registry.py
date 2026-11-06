from pathlib import Path

from blackpearl.providers.base import MediaInfo, MediaProvider
from blackpearl.providers.registry import ProviderRegistry


class ExampleProvider(MediaProvider):
    def can_handle(self, url: str) -> bool:
        return "example.com" in url

    def get_info(self, url: str) -> MediaInfo:
        return MediaInfo(
            title="Example",
            url=url,
            media_type="video",
        )

    def download(self, url: str, output_path: Path) -> None:
        pass


def test_registry_returns_matching_provider():
    registry = ProviderRegistry()
    provider = ExampleProvider()

    registry.register(provider)

    result = registry.get_provider("https://example.com/video")

    assert result is provider


def test_registry_returns_none_for_unknown_url():
    registry = ProviderRegistry()
    registry.register(ExampleProvider())

    result = registry.get_provider("https://unknown.com/video")

    assert result is None


def test_registry_without_providers():
    registry = ProviderRegistry()

    result = registry.get_provider("https://example.com/video")

    assert result is None
