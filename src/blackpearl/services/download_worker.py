from dataclasses import dataclass, field
from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, Signal, Slot

from blackpearl.providers.base import (
    DownloadCancelled,
    DownloadOptions,
    MediaProvider,
)


@dataclass(frozen=True)
class DownloadJob:
    """Один элемент очереди загрузки."""

    url: str
    title: str


@dataclass(frozen=True)
class DownloadSummary:
    """Итог выполнения очереди."""

    total: int
    succeeded: int
    # Не скачанные треки: (название, текст ошибки).
    failed: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    cancelled: bool = False


class DownloadQueueWorker(QObject):
    """Последовательно скачивает очередь в фоновом потоке.

    Ошибка одного трека не останавливает очередь. Отмена действует
    на всю очередь целиком: один cancel_event на всё время работы,
    поэтому отмена между треками не теряется.
    """

    track_started = Signal(int, int, str)  # индекс, всего, название
    progress_changed = Signal(float)  # общий прогресс очереди, 0–100
    queue_finished = Signal(object)  # DownloadSummary
    finished = Signal()

    def __init__(
        self,
        provider: MediaProvider,
        jobs: list[DownloadJob],
        output_dir: Path,
        options: DownloadOptions,
        cancel_event: Event,
    ) -> None:
        super().__init__()
        self.provider = provider
        self.jobs = list(jobs)
        self.output_dir = output_dir
        self.options = options
        self.cancel_event = cancel_event

    @Slot()
    def run(self) -> None:
        try:
            self.queue_finished.emit(self._run_queue())
        finally:
            self.finished.emit()

    def _run_queue(self) -> DownloadSummary:
        total = len(self.jobs)
        succeeded = 0
        failed: list[tuple[str, str]] = []
        cancelled = False

        for index, job in enumerate(self.jobs):
            if self.cancel_event.is_set():
                cancelled = True
                break

            self.track_started.emit(index, total, job.title)
            self.progress_changed.emit(index / total * 100)

            def on_progress(percent: float, index: int = index) -> None:
                self.progress_changed.emit((index + percent / 100) / total * 100)

            try:
                self.provider.download(
                    url=job.url,
                    output_dir=self.output_dir,
                    options=self.options,
                    progress_callback=on_progress,
                    cancel_event=self.cancel_event,
                )
            except DownloadCancelled:
                cancelled = True
                break
            except Exception as error:
                failed.append((job.title, str(error) or type(error).__name__))
            else:
                succeeded += 1

        if not cancelled:
            self.progress_changed.emit(100.0)

        return DownloadSummary(
            total=total,
            succeeded=succeeded,
            failed=tuple(failed),
            cancelled=cancelled,
        )
