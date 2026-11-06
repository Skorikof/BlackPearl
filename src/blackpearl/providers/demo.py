from pathlib import Path

from blackpearl.providers.base import MediaInfo, MediaProvider


class DemoProvider(MediaProvider):
    def can_handle(self, url: str) -> bool:
        return "example.com" in url

    def get_info(self, url: str) -> MediaInfo:
        return MediaInfo(
            title="Demo media",
            url=url,
            media_type="video",
        )

    def download(self, url: str, output_path: Path) -> None:
        raise NotImplementedError(
            "DemoProvider does not support downloading"
        )
