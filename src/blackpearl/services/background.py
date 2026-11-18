from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot


def start_in_thread(
    worker: QObject,
    parent: QObject,
    on_thread_finished: Callable[[], None],
) -> QThread:
    """Запускает worker.run() в новом QThread.

    worker должен иметь слот run() и сигнал finished, который
    испускается в конце run(). После него поток останавливается,
    а worker и поток удаляются через deleteLater.

    on_thread_finished должен быть слотом объекта, живущего в главном
    потоке (связанным методом QObject): тогда Qt вызовет его в главном
    потоке. В нём нужно вызвать thread.wait() — сигнал finished
    испускается чуть раньше фактического выхода из потока.
    """
    thread = QThread(parent)
    worker.moveToThread(thread)

    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.finished.connect(on_thread_finished)

    thread.start()
    return thread


class _CallWorker(QObject):
    """Вызывает функцию в фоновом потоке и сообщает результат."""

    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, function: Callable[[], Any]) -> None:
        super().__init__()
        self._function = function

    @Slot()
    def run(self) -> None:
        try:
            result = self._function()
        except Exception as error:
            self.failed.emit(str(error) or type(error).__name__)
        else:
            self.succeeded.emit(result)
        finally:
            self.finished.emit()


class BackgroundTask(QObject):
    """Выполняет одну функцию за раз в фоновом потоке.

    Колбэки on_success и on_error вызываются в главном потоке,
    поэтому из них можно работать с виджетами. Сигнал finished
    приходит после полной остановки потока: в его обработчике
    is_running уже False.
    """

    finished = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: _CallWorker | None = None
        self._on_success: Callable[[Any], None] | None = None
        self._on_error: Callable[[str], None] | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None

    def start(
        self,
        function: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        """Запускает function() в фоне.

        function выполняется в фоновом потоке и не должна
        обращаться к виджетам.
        """
        if self._thread is not None:
            raise RuntimeError("Фоновая задача уже выполняется")

        self._on_success = on_success
        self._on_error = on_error
        self._worker = _CallWorker(function)
        self._worker.succeeded.connect(self._handle_success)
        self._worker.failed.connect(self._handle_error)
        self._thread = start_in_thread(
            self._worker, self, self._handle_thread_finished
        )

    @Slot(object)
    def _handle_success(self, result: Any) -> None:
        if self._on_success is not None:
            self._on_success(result)

    @Slot(str)
    def _handle_error(self, message: str) -> None:
        if self._on_error is not None:
            self._on_error(message)

    @Slot()
    def _handle_thread_finished(self) -> None:
        if self._thread is not None:
            self._thread.wait()
        self._thread = None
        self._worker = None
        self._on_success = None
        self._on_error = None
        self.finished.emit()
