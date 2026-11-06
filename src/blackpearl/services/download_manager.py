from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, QThread, Signal

from blackpearl.providers.base import MediaProvider
from blackpearl.services.download_worker import DownloadWorker


class DownloadManager(QObject):
    progress_changed = Signal(float)
    completed = Signal()
    cancelled = Signal()
    error_occurred = Signal(str)

    def __init__(self) -> None:
        super().__init__()

        self._thread: QThread | None = None
        self._worker: DownloadWorker | None = None
        self._cancel_event: Event | None = None

    def start_download(
        self,
        provider: MediaProvider,
        url: str,
        output_dir: Path,
        audio_bitrate_kbps: int = 192,
    ) -> None:
        if self._thread is not None:
            raise RuntimeError("Загрузка уже выполняется")

        self._cancel_event = Event()
        self._thread = QThread(self)

        self._worker = DownloadWorker(
            provider=provider,
            url=url,
            output_dir=output_dir,
            cancel_event=self._cancel_event,
            audio_bitrate_kbps=audio_bitrate_kbps,
        )

        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)

        self._worker.progress_changed.connect(self.progress_changed)
        self._worker.completed.connect(self.completed)
        self._worker.cancelled.connect(self.cancelled)
        self._worker.error_occurred.connect(self.error_occurred)

        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)

        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._cleanup)

        self._thread.start()

    def cancel_download(self) -> None:
        if self._cancel_event is not None:
            self._cancel_event.set()

    def _cleanup(self) -> None:
        self._worker = None
        self._thread = None
        self._cancel_event = None
