from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, QThread, Signal, Slot

from blackpearl.providers.base import DownloadOptions, MediaProvider
from blackpearl.services.background import start_in_thread
from blackpearl.services.download_worker import (
    DownloadJob,
    DownloadQueueWorker,
    DownloadSummary,
)


class DownloadManager(QObject):
    """Запускает очередь загрузок в фоновом потоке.

    Сигнал finished приходит, когда поток полностью остановлен:
    в его обработчике is_busy уже False и можно сразу запускать
    новую очередь или закрывать приложение.
    """

    track_started = Signal(int, int, str)  # индекс, всего, название
    progress_changed = Signal(float)  # общий прогресс очереди, 0–100
    finished = Signal(object)  # DownloadSummary

    def __init__(self) -> None:
        super().__init__()

        self._thread: QThread | None = None
        self._worker: DownloadQueueWorker | None = None
        self._cancel_event: Event | None = None
        self._summary: DownloadSummary | None = None

    @property
    def is_busy(self) -> bool:
        """Выполняется ли сейчас очередь."""
        return self._thread is not None

    def start(
        self,
        provider: MediaProvider,
        jobs: list[DownloadJob],
        output_dir: Path,
        options: DownloadOptions,
    ) -> None:
        if self._thread is not None:
            raise RuntimeError("Загрузка уже выполняется")
        if not jobs:
            raise ValueError("Очередь загрузки пуста")

        self._cancel_event = Event()
        self._summary = None
        self._worker = DownloadQueueWorker(
            provider=provider,
            jobs=jobs,
            output_dir=output_dir,
            options=options,
            cancel_event=self._cancel_event,
        )
        self._worker.track_started.connect(self.track_started)
        self._worker.progress_changed.connect(self.progress_changed)
        self._worker.queue_finished.connect(self._store_summary)

        self._thread = start_in_thread(self._worker, self, self._cleanup)

    def cancel(self) -> None:
        if self._cancel_event is not None:
            self._cancel_event.set()

    @Slot(object)
    def _store_summary(self, summary: DownloadSummary) -> None:
        self._summary = summary

    @Slot()
    def _cleanup(self) -> None:
        if self._thread is not None:
            # finished испускается до фактического выхода из потока;
            # дожидаемся его, чтобы поток можно было безопасно удалить.
            self._thread.wait()
        summary = self._summary or DownloadSummary(
            total=0, succeeded=0, cancelled=True
        )
        self._worker = None
        self._thread = None
        self._cancel_event = None
        self._summary = None

        self.finished.emit(summary)
