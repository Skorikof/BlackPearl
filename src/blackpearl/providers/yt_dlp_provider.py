from pathlib import Path
from threading import Event
from urllib.parse import urlparse

import yt_dlp

from blackpearl.core.ffmpeg import require_ffmpeg
from blackpearl.providers.base import (
    DownloadOptions,
    MediaInfo,
    MediaProvider,
    ProgressCallback,
)


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

    @staticmethod
    def _build_format_options(
        options: DownloadOptions,
        ffmpeg_location: str,
    ) -> dict:
        """Опции yt-dlp, зависящие от режима скачивания."""
        if options.kind == "audio":
            return {
                "format": "bestaudio/best",
                "ffmpeg_location": ffmpeg_location,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": str(options.audio_bitrate_kbps),
                    }
                ],
            }

        height = options.video_max_height
        if height is not None:
            video_format = (
                f"bestvideo[height<={height}]+bestaudio"
                f"/best[height<={height}]"
            )
        else:
            video_format = "bestvideo+bestaudio/best"

        return {
            "format": video_format,
            "ffmpeg_location": ffmpeg_location,
            "merge_output_format": "mp4",
        }

    def download(
        self,
        url: str,
        output_dir: Path,
        options: DownloadOptions,
        progress_callback: ProgressCallback | None = None,
        cancel_event: Event | None = None,
        ) -> None:
        # ffmpeg нужен и для конвертации в mp3, и для склейки видео с аудио;
        # проверяем заранее, чтобы не скачивать файл впустую.
        ffmpeg_location = require_ffmpeg()
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

        ydl_options = {
            "paths": {"home": str(output_dir)},
            "outtmpl": "%(title)s.%(ext)s",
            "noplaylist": True,
            "progress_hooks": [progress_hook],
            **self._build_format_options(options, ffmpeg_location),
        }

        with yt_dlp.YoutubeDL(ydl_options) as downloader:
            downloader.download([url])

