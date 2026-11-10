from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import Qt, QThread, Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
)

from blackpearl.providers.base import TrackEntry
from blackpearl.providers.registry import ProviderRegistry
from blackpearl.providers.yandex_music_provider import YandexMusicProvider
from blackpearl.providers.yt_dlp_provider import YtDlpProvider
from blackpearl.services.collection_worker import CollectionWorker
from blackpearl.services.download_manager import DownloadManager
from blackpearl.services.info_worker import InfoWorker
from blackpearl.ui.ui_py.main_ui import Ui_MainWindow
from blackpearl.ui.widgets.audio_table import AudioTable


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self._info_thread: QThread | None = None
        self._info_worker: InfoWorker | None = None
        self._collection_thread: QThread | None = None
        self._collection_worker: CollectionWorker | None = None
        self._table = AudioTable(self.ui.audio_tableWidget)

        self._current_provider = None
        self._current_url = ""
        self._table_entries: list[TrackEntry | str] = []

        self._download_queue: list[TrackEntry | str] = []
        self._queue_total = 0
        self._queue_index = 0
        self._waiting_for_manager = False
        self._output_dir: Path | None = None

        self.registry = ProviderRegistry()
        self.registry.register(YandexMusicProvider())
        self.registry.register(YtDlpProvider())

        self.download_manager = DownloadManager()
        self._configure_ui()
        self._connect_signals()

    def _configure_ui(self) -> None:
        self.ui.audio_download_btn.setEnabled(False)
        self.ui.audio_cancel_btn.setEnabled(False)
        self.ui.audio_check_all_btn.setEnabled(False)
        self.ui.audio_remove_all_btn.setEnabled(False)

        for index, bitrate in enumerate((128, 192, 320)):
            self.ui.audio_quality_cb.setItemData(index, bitrate)
        self.ui.audio_quality_cb.setCurrentIndex(2)

        self.ui.stackedWidget.setCurrentWidget(self.ui.audio_page)

    def _connect_signals(self) -> None:
        self.ui.main_audio_btn.clicked.connect(
            lambda: self.ui.stackedWidget.setCurrentWidget(self.ui.audio_page)
        )
        for button in (
            self.ui.in_dev_btn,
            self.ui.in_dev_btn_2,
            self.ui.in_dev_btn_3,
            self.ui.in_dev_btn_4,
            self.ui.in_dev_btn_5,
        ):
            button.clicked.connect(
                lambda checked=False: self.ui.stackedWidget.setCurrentWidget(
                    self.ui.dev_page
                )
            )

        self.ui.audio_check_btn.clicked.connect(self.check_url)
        self.ui.audio_download_btn.clicked.connect(self.start_download)
        self.ui.audio_cancel_btn.clicked.connect(
            self.download_manager.cancel_download
        )
        self.ui.audio_check_all_btn.clicked.connect(self.select_all_tracks)
        self.ui.audio_remove_all_btn.clicked.connect(self.select_no_tracks)
        self.ui.audio_tableWidget.itemChanged.connect(
            self._update_table_controls
        )

        self.download_manager.progress_changed.connect(self.update_progress)
        self.download_manager.completed.connect(self.download_completed)
        self.download_manager.cancelled.connect(self.download_cancelled)
        self.download_manager.error_occurred.connect(self.download_error)
        self.download_manager.ready.connect(self._handle_download_manager_ready)

    def _set_status(self, message: str) -> None:
        self.ui.audio_label.setText(message)

    def _clear_table(self) -> None:
        self._table_entries.clear()
        self._table.set_row_count(0)
        self.ui.audio_check_all_btn.setEnabled(False)
        self.ui.audio_remove_all_btn.setEnabled(False)
        self.ui.audio_download_btn.setEnabled(False)

    def _update_table_controls(self) -> None:
        flag_all, has_selected = self._table.update_table_controls()
        self.ui.audio_check_all_btn.setEnabled(flag_all)
        self.ui.audio_remove_all_btn.setEnabled(flag_all)
        self.ui.audio_download_btn.setEnabled(has_selected)

    def check_url(self) -> None:
        self._clear_table()
        self._current_provider = None
        self._current_url = ""

        url = self.ui.audio_url_le.text().strip()
        if not url:
            self._set_status("Введите ссылку")
            return

        provider = self.registry.get_provider(url)
        if provider is None:
            self._set_status("Источник не поддерживается")
            return

        self._current_provider = provider
        self._current_url = url
        self.ui.audio_check_btn.setEnabled(False)

        if isinstance(provider, YandexMusicProvider):
            path = urlparse(url).path
            is_track = bool(
                provider.TRACK_PATTERN.search(path)
                or provider.TRACK_IN_ALBUM_PATTERN.search(path)
            )
            is_collection = bool(
                provider.ALBUM_PATTERN.fullmatch(path)
                or provider.PLAYLIST_PATTERN.search(path)
                or provider.PLAYLIST_UUID_PATTERN.search(path)
                or provider.ARTIST_TRACKS_PATTERN.fullmatch(path)
            )
            if is_collection and not is_track:
                self.load_collection(provider, url)
                return

        self._set_status("Получаю информацию...")
        self._info_thread = QThread(self)
        self._info_worker = InfoWorker(provider, url)
        self._info_worker.moveToThread(self._info_thread)

        self._info_thread.started.connect(self._info_worker.run)
        self._info_worker.info_ready.connect(self.show_info)
        self._info_worker.error_occurred.connect(self.show_error)
        self._info_worker.finished.connect(self._info_thread.quit)
        self._info_worker.finished.connect(self._info_worker.deleteLater)
        self._info_thread.finished.connect(self._info_thread.deleteLater)
        self._info_thread.finished.connect(self._handle_info_thread_finished)
        self._info_thread.start()

    @Slot(object)
    def show_info(self, info) -> None:
        self._table_entries = [self._current_url]
        self._table.set_row_count(1)
        self._table.add_table_row(
            0,
            "",
            info.title,
            info.duration_seconds,
        )
        self._update_table_controls()
        self._set_status(f"Найдено: {info.title}")

    @Slot(str)
    def show_error(self, message: str) -> None:
        self._clear_table()
        self._set_status(f"Не удалось получить информацию: {message}")

    @Slot()
    def _handle_info_thread_finished(self) -> None:
        self.ui.audio_check_btn.setEnabled(True)
        self._info_worker = None
        self._info_thread = None

    def load_collection(self, provider: YandexMusicProvider, url: str) -> None:
        self._set_status("Получаю список треков...")
        self._collection_thread = QThread(self)
        self._collection_worker = CollectionWorker(provider, url)
        self._collection_worker.moveToThread(self._collection_thread)

        self._collection_thread.started.connect(self._collection_worker.run)
        self._collection_worker.tracks_ready.connect(self.show_collection)
        self._collection_worker.error_occurred.connect(self.show_error)
        self._collection_worker.finished.connect(self._collection_thread.quit)
        self._collection_worker.finished.connect(
            self._collection_worker.deleteLater
        )
        self._collection_thread.finished.connect(
            self._collection_thread.deleteLater
        )
        self._collection_thread.finished.connect(
            self._handle_collection_thread_finished
        )
        self._collection_thread.start()

    @Slot(object)
    def show_collection(self, tracks: list[TrackEntry]) -> None:
        self._table_entries = list(tracks)
        self._table.set_row_count(len(tracks))

        for row, track in enumerate(tracks):
            self._table.add_table_row(
                row,
                track.artists,
                track.title,
                track.duration_seconds,
            )

        self._update_table_controls()
        self._set_status(f"Найдено треков: {len(tracks)}")

    @Slot()
    def _handle_collection_thread_finished(self) -> None:
        self.ui.audio_check_btn.setEnabled(True)
        self._collection_worker = None
        self._collection_thread = None

    def select_all_tracks(self) -> None:
        for row in range(self._table.get_row_count()):
            item = self._table.get_item(row, 0)
            if item is not None:
                item.setCheckState(Qt.CheckState.Checked)
        self._update_table_controls()

    def select_no_tracks(self) -> None:
        for row in range(self._table.get_row_count()):
            item = self._table.get_item(row, 0)
            if item is not None:
                item.setCheckState(Qt.CheckState.Unchecked)
        self._update_table_controls()

    def start_download(self) -> None:
        if self._current_provider is None or not self._table_entries:
            return

        output_dir = QFileDialog.getExistingDirectory(
            self,
            "Выбери папку для сохранения музыки",
        )
        if not output_dir:
            return
        self._output_dir = Path(output_dir)

        self._download_queue = [
            self._table_entries[row]
            for row in range(self._table.get_row_count())
            if self._table.get_item(row, 0) is not None
            and self._table.get_item(row, 0).checkState()
            == Qt.CheckState.Checked
        ]
        if not self._download_queue:
            self._set_status("Выбери хотя бы один трек")
            return

        self._queue_total = len(self._download_queue)
        self._queue_index = 0
        self._waiting_for_manager = False
        self.ui.audio_download_btn.setEnabled(False)
        self.ui.audio_cancel_btn.setEnabled(True)
        self.ui.audio_progressBar.setValue(0)
        self._start_next_track()

    def _start_next_track(self) -> None:
        if self._queue_index >= self._queue_total:
            self._finish_queue()
            return

        item = self._download_queue[self._queue_index]
        if isinstance(item, str):
            url = item
            title = "Медиа"
        else:
            url = item.url
            title = f"{item.artists} — {item.title}"

        self._set_status(
            f"Скачивание {self._queue_index + 1} из {self._queue_total}: {title}"
        )
        try:
            self.download_manager.start_download(
                provider=self._current_provider,
                url=url,
                output_dir=self._output_dir,
                audio_bitrate_kbps=self.ui.audio_quality_cb.currentData(),
            )
        except RuntimeError as error:
            self._set_status(str(error))
            self.ui.audio_download_btn.setEnabled(True)
            self.ui.audio_cancel_btn.setEnabled(False)

    @Slot(float)
    def update_progress(self, percent: float) -> None:
        if self._queue_total == 0:
            self.ui.audio_progressBar.setValue(round(percent))
            return
        overall = (self._queue_index + percent / 100) / self._queue_total * 100
        self.ui.audio_progressBar.setValue(round(overall))

    @Slot()
    def download_completed(self) -> None:
        self._queue_index += 1
        self._waiting_for_manager = True

    @Slot()
    def _handle_download_manager_ready(self) -> None:
        if not self._waiting_for_manager:
            return
        self._waiting_for_manager = False
        if self._queue_index < self._queue_total:
            self._start_next_track()
        else:
            self._finish_queue()

    def _finish_queue(self) -> None:
        self.ui.audio_progressBar.setValue(100)
        self._set_status(f"Загрузка завершена. Скачано треков: {self._queue_total}")
        self.ui.audio_download_btn.setEnabled(True)
        self.ui.audio_cancel_btn.setEnabled(False)
        self._download_queue.clear()

    @Slot()
    def download_cancelled(self) -> None:
        self._waiting_for_manager = False
        self._download_queue.clear()
        self._set_status("Загрузка отменена")
        self.ui.audio_download_btn.setEnabled(True)
        self.ui.audio_cancel_btn.setEnabled(False)

    @Slot(str)
    def download_error(self, message: str) -> None:
        self._waiting_for_manager = False
        self._download_queue.clear()
        self._set_status(f"Ошибка загрузки: {message}")
        self.ui.audio_download_btn.setEnabled(True)
        self.ui.audio_cancel_btn.setEnabled(False)
