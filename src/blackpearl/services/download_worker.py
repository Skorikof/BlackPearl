from pathlib import Path
from threading import Event

import yt_dlp
from PySide6.QtCore import QObject, Signal, Slot

from blackpearl.providers.base import MediaProvider


class DownloadWorker(QObject):
    progress_changed = Signal(float)
    completed = Signal()
    cancelled = Signal()
    error_occurred = Signal(str)
    finished = Signal()

    def __init__(
        self,
        provider: MediaProvider,
        url: str,
        audio_bitrate_kbps: int,
        output_dir: Path,
        cancel_event: Event,
    ) -> None:
        super().__init__()
        self.provider = provider
        self.url = url
        self.audio_bitrate_kbps = audio_bitrate_kbps
        self.output_dir = output_dir
        self.cancel_event = cancel_event

    @Slot()
    def run(self) -> None:
        try:
            self.provider.download(
                url=self.url,
                output_dir=self.output_dir,
                audio_bitrate_kbps=self.audio_bitrate_kbps,
                progress_callback=self.progress_changed.emit,
                cancel_event=self.cancel_event,
            )

            if self.cancel_event.is_set():
                self.cancelled.emit()
            else:
                self.completed.emit()

        except yt_dlp.utils.DownloadCancelled:
            self.cancelled.emit()

        except Exception as error:
            self.error_occurred.emit(str(error))

        finally:
            self.finished.emit()
