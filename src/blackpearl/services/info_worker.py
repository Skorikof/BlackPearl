from PySide6.QtCore import QObject, Signal, Slot

from blackpearl.providers.base import MediaInfo, MediaProvider


class InfoWorker(QObject):
    """Получает информацию о медиа в отдельном потоке."""

    info_ready = Signal(object)
    error_occurred = Signal(str)
    finished = Signal()

    def __init__(self, provider: MediaProvider, url: str) -> None:
        super().__init__()
        self.provider = provider
        self.url = url

    @Slot()
    def run(self) -> None:
        try:
            info: MediaInfo = self.provider.get_info(self.url)
            self.info_ready.emit(info)

        except Exception as error:
            self.error_occurred.emit(str(error))

        finally:
            self.finished.emit()
