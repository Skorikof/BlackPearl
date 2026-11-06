from pathlib import Path
from threading import Event
from urllib.parse import urlparse

import yt_dlp

from blackpearl.providers.base import MediaInfo, MediaProvider, ProgressCallback


class YtDlpProvider(MediaProvider):
    """Провайдер, использующий yt-dlp."""

    def can_handle(self, url: str) -> bool:
        parsed_url = urlparse(url)

        return (
            parsed_url.scheme in {"http", "https"}
            and bool(parsed_url.netloc)
        )

    def get_info(self, url: str) -> MediaInfo:
        options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
        }

        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, download=False)

        if info is None:
            raise RuntimeError("Не удалось получить информацию о медиа")

        media_type = (
            "audio"
            if info.get("vcodec") == "none"
            else "video"
        )

        return MediaInfo(
            title=info.get("title") or "Без названия",
            url=url,
            media_type=media_type,
            duration_seconds=info.get("duration"),
        )

    
    def download(
        self,
        url: str,
        output_dir: Path,
        progress_callback: ProgressCallback | None = None,
        cancel_event: Event | None = None,
        ) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)

        def progress_hook(data: dict) -> None:
            if cancel_event is not None and cancel_event.is_set():
                raise yt_dlp.utils.DownloadCancelled(
                    "Загрузка отменена пользователем"
                )

            if data.get("status") != "downloading":
                return

            downloaded = data.get("downloaded_bytes", 0)
            total = (
                data.get("total_bytes")
                or data.get("total_bytes_estimate")
            )

            if total and progress_callback is not None:
                percent = downloaded / total * 100
                progress_callback(min(percent, 100.0))

        options = {
            "paths": {"home": str(output_dir)},
            "outtmpl": "%(title)s.%(ext)s",
            "noplaylist": True,
            "progress_hooks": [progress_hook],
        }

        with yt_dlp.YoutubeDL(options) as downloader:
            downloader.download([url])

