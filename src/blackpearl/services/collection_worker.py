from PySide6.QtCore import QObject, Signal, Slot

from blackpearl.providers.yandex_music_provider import (
    YandexMusicProvider,
)


class CollectionWorker(QObject):
    tracks_ready = Signal(object)
    error_occurred = Signal(str)
    finished = Signal()

    def __init__(
        self,
        provider: YandexMusicProvider,
        url: str,
    ) -> None:
        super().__init__()
        self.provider = provider
        self.url = url

    @Slot()
    def run(self) -> None:
        try:
            tracks = self.provider.get_collection_tracks(
                self.url
            )
            self.tracks_ready.emit(tracks)

        except Exception as error:
            self.error_occurred.emit(str(error))

        finally:
            self.finished.emit()
