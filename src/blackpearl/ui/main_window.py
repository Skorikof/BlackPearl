from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import Qt, QThread, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from blackpearl.providers.registry import ProviderRegistry
from blackpearl.providers.yandex_music_provider import YandexMusicProvider
from blackpearl.providers.yt_dlp_provider import YtDlpProvider
from blackpearl.services.collection_worker import CollectionWorker
from blackpearl.services.download_manager import DownloadManager
from blackpearl.services.info_worker import InfoWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        
        self._waiting_for_manager = False
        self._download_queue = []
        self._queue_total = 0
        self._queue_index = 0
        self._output_dir: Path | None = None

        self.setWindowTitle("BlackPearl")
        self.resize(900, 600)

        self.registry = ProviderRegistry()
        self.registry.register(YandexMusicProvider())
        self.registry.register(YtDlpProvider())
        
        self._info_thread: QThread | None = None
        self._info_worker: InfoWorker | None = None
        self._collection_thread: QThread | None = None
        self._collection_worker: CollectionWorker | None = None
        self._tracks = []

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Вставь ссылку на медиа")

        self.check_button = QPushButton("Проверить источник")
        self.check_button.clicked.connect(self.check_url)

        self.status_label = QLabel("Ожидаю ссылку...")
        
        self.download_button = QPushButton("Скачать")
        self.cancel_button = QPushButton("Отмена")

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.download_button.setEnabled(False)
        self.cancel_button.setEnabled(False)

        self.download_manager = DownloadManager()
        self.download_button.clicked.connect(self.start_download)
        self.cancel_button.clicked.connect(
            self.download_manager.cancel_download
        )

        self.download_manager.progress_changed.connect(
            self.update_progress
        )
        self.download_manager.completed.connect(
            self.download_completed
        )
        self.download_manager.cancelled.connect(
            self.download_cancelled
        )
        self.download_manager.error_occurred.connect(
            self.download_error
        )
        self.download_manager.ready.connect(
            self.on_download_manager_ready
        )

        layout = QVBoxLayout()
        layout.addWidget(self.url_input)
        layout.addWidget(self.check_button)

        download_buttons = QHBoxLayout()
        download_buttons.addWidget(self.download_button)
        download_buttons.addWidget(self.cancel_button)

        layout.addLayout(download_buttons)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        
        self.quality_combo = QComboBox()

        self.quality_combo.addItem("128 кбит/с", 128)
        self.quality_combo.addItem("192 кбит/с", 192)
        self.quality_combo.addItem("320 кбит/с", 320)

        self.quality_combo.setCurrentIndex(1)
        
        layout.addWidget(self.quality_combo)
        
        self.track_table = QTableWidget(0, 4)

        self.track_table.setHorizontalHeaderLabels([
            " ",
            "Исполнитель",
            "Название",
            "Длительность",
        ])

        self.track_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.track_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.track_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.track_table.setColumnWidth(0, 40)

        layout.addWidget(self.track_table)

        self.select_all_button = QPushButton("Выбрать всё")
        self.select_none_button = QPushButton("Снять выделение")

        selection_buttons = QHBoxLayout()

        selection_buttons.addWidget(self.select_all_button)
        selection_buttons.addWidget(self.select_none_button)

        layout.addLayout(selection_buttons)

        self.select_all_button.clicked.connect(
            self.select_all_tracks
        )

        self.select_none_button.clicked.connect(
            self.select_no_tracks
        )

        self.track_table.setVisible(False)
        self.select_all_button.setVisible(False)
        self.select_none_button.setVisible(False)

        central_widget = QWidget()
        central_widget.setLayout(layout)

        self.setCentralWidget(central_widget)
        
        self._current_provider = None
        self._current_url = ""
        self.download_button.setEnabled(False)
        self.cancel_button.setEnabled(False)

    def check_url(self) -> None:
        self.download_button.setEnabled(False)
        url = self.url_input.text().strip()
        if not url:
            self.status_label.setText("Введите ссылку")
            return

        provider = self.registry.get_provider(url)
        if provider is None:
            self.status_label.setText("Источник не поддерживается")
            return
        self._current_provider = provider
        self._current_url = url
        if isinstance(provider, YandexMusicProvider):
            path = urlparse(url).path

            is_track = (
                provider.TRACK_PATTERN.search(path)
                or provider.TRACK_IN_ALBUM_PATTERN.search(path)
            )

            is_collection = (
                provider.ALBUM_PATTERN.fullmatch(path)
                or provider.PLAYLIST_PATTERN.search(path)
                or provider.PLAYLIST_UUID_PATTERN.search(path)
            )

            if is_collection and not is_track:
                self.load_collection(provider, url)
                return
        
        # Не допускаем повторного запуска,
        # пока предыдущий запрос не завершён.
        self.check_button.setEnabled(False)
        self.status_label.setText("Получаю информацию...")

        self._info_thread = QThread(self)
        self._info_worker = InfoWorker(provider, url)

        self._info_worker.moveToThread(self._info_thread)

        self._info_thread.started.connect(self._info_worker.run)

        self._info_worker.info_ready.connect(self.show_info)
        self._info_worker.error_occurred.connect(self.show_error)

        self._info_worker.finished.connect(self._info_thread.quit)
        self._info_worker.finished.connect(
            self._info_worker.deleteLater
        )

        self._info_thread.finished.connect(
            self._info_thread.deleteLater
        )
        self._info_thread.finished.connect(
            self.on_info_thread_finished
        )

        self._info_thread.start()
        
    def _start_next_track(self) -> None:
        if self._queue_index >= self._queue_total:
            self.download_completed()
            return
        item = self._download_queue[self._queue_index]
        if isinstance(item, str):
            url = item
            title = "Медиа"
        else:
            url = item.url
            title = f"{item.artists} — {item.title}"
        self.status_label.setText(
            f"Скачивание {self._queue_index + 1} "
            f"из {self._queue_total}: {title}"
        )
        try:
            self.download_manager.start_download(
                provider=self._current_provider,
                url=url,
                output_dir=self._output_dir,
                audio_bitrate_kbps=self.quality_combo.currentData(),
            )
        except RuntimeError as error:
            self.status_label.setText(str(error))
            self.download_button.setEnabled(True)
            self.cancel_button.setEnabled(False)

    @Slot(object)
    def show_info(self, info) -> None:
        self.status_label.setText(
            f"Название: {info.title}\n"
            f"Тип: {info.media_type}\n"
            f"Длительность: {info.duration_seconds}"
        )
        self.download_button.setEnabled(self._current_provider is not None)

    @Slot(str)
    def show_error(self, message: str) -> None:
        self.status_label.setText(
            f"Не удалось получить информацию: {message}"
        )

    @Slot()
    def on_info_thread_finished(self) -> None:
        self.check_button.setEnabled(True)
        self._info_worker = None
        self._info_thread = None

    @Slot()
    def start_download(self) -> None:
        if self._current_provider is None:
            return
        output_dir = QFileDialog.getExistingDirectory(
            self,
            "Выбери папку для сохранения музыки",
        )
        if not output_dir:
            return
        self._output_dir = Path(output_dir)
        # Если открыта таблица коллекции — скачиваем выбранные треки.
        if self.track_table.isVisible():
            self._download_queue = [
                self._tracks[row]
                for row in range(self.track_table.rowCount())
                if self.track_table.item(row, 0).checkState()
                == Qt.CheckState.Checked
            ]
            if not self._download_queue:
                self.status_label.setText(
                    "Выбери хотя бы один трек"
                )
                return
        else:
            # Обычная одиночная ссылка.
            self._download_queue = [self._current_url]
        self._queue_total = len(self._download_queue)
        self._queue_index = 0
        self.download_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self._start_next_track()
            
    @Slot(float)
    def update_progress(self, percent: float) -> None:
        if self._queue_total == 0:
            self.progress_bar.setValue(round(percent))
            return
        overall_progress = (
            self._queue_index + percent / 100
        ) / self._queue_total * 100
        self.progress_bar.setValue(round(overall_progress))
        
    @Slot()
    def download_completed(self) -> None:
        self._queue_index += 1
        self._waiting_for_manager = True
        
        # if self._queue_index < self._queue_total:
        #     self._start_next_track()
        #     return
        # self.progress_bar.setValue(100)
        # self.status_label.setText(
        #     f"Загрузка завершена. "
        #     f"Скачано треков: {self._queue_total}"
        # )
        # self.download_button.setEnabled(True)
        # self.cancel_button.setEnabled(False)
        # self._download_queue.clear()
        
    @Slot()
    def on_download_manager_ready(self) -> None:
        if not self._waiting_for_manager:
            return
        self._waiting_for_manager = False
        if self._queue_index < self._queue_total:
            self._start_next_track()
            return
        self.progress_bar.setValue(100)
        self.status_label.setText(
            f"Загрузка завершена. "
            f"Скачано треков: {self._queue_total}"
        )
        self.download_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

    @Slot()
    def download_cancelled(self) -> None:
        self.status_label.setText("Загрузка отменена")
        self.download_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

    @Slot(str)
    def download_error(self, message: str) -> None:
        self.status_label.setText(f"Ошибка загрузки: {message}")
        self.download_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        
    def load_collection(
        self,
        provider: YandexMusicProvider,
        url: str,
    ) -> None:
        self.check_button.setEnabled(False)
        self.download_button.setEnabled(False)

        self.track_table.setVisible(False)
        self.select_all_button.setVisible(False)
        self.select_none_button.setVisible(False)

        self.status_label.setText(
            "Получаю список треков..."
        )

        self._collection_thread = QThread(self)

        self._collection_worker = CollectionWorker(
            provider,
            url,
        )

        self._collection_worker.moveToThread(
            self._collection_thread
        )

        self._collection_thread.started.connect(
            self._collection_worker.run
        )

        self._collection_worker.tracks_ready.connect(
            self.show_collection
        )

        self._collection_worker.error_occurred.connect(
            self.show_error
        )

        self._collection_worker.finished.connect(
            self._collection_thread.quit
        )

        self._collection_worker.finished.connect(
            self._collection_worker.deleteLater
        )

        self._collection_thread.finished.connect(
            self._collection_thread.deleteLater
        )

        self._collection_thread.finished.connect(
            self.on_collection_thread_finished
        )

        self._collection_thread.start()


    @Slot(object)
    def show_collection(self, tracks) -> None:
        self._tracks = tracks

        self.track_table.setRowCount(len(tracks))

        for row, track in enumerate(tracks):
            checkbox = QTableWidgetItem()

            checkbox.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsUserCheckable
            )

            checkbox.setCheckState(
                Qt.CheckState.Checked
            )

            self.track_table.setItem(row, 0, checkbox)

            self.track_table.setItem(
                row,
                1,
                QTableWidgetItem(track.artists),
            )

            self.track_table.setItem(
                row,
                2,
                QTableWidgetItem(track.title),
            )

            duration = ""

            if track.duration_seconds is not None:
                minutes, seconds = divmod(
                    int(track.duration_seconds),
                    60,
                )

                duration = f"{minutes}:{seconds:02d}"

            self.track_table.setItem(
                row,
                3,
                QTableWidgetItem(duration),
            )

        self.track_table.setVisible(True)
        self.select_all_button.setVisible(True)
        self.select_none_button.setVisible(True)

        self.status_label.setText(
            f"Найдено треков: {len(tracks)}"
        )
        
        self.download_button.setEnabled(bool(tracks))

    @Slot()
    def on_collection_thread_finished(self) -> None:
        self.check_button.setEnabled(True)

        self._collection_worker = None
        self._collection_thread = None


    def select_all_tracks(self) -> None:
        for row in range(self.track_table.rowCount()):
            item = self.track_table.item(row, 0)

            if item is not None:
                item.setCheckState(Qt.CheckState.Checked)


    def select_no_tracks(self) -> None:
        for row in range(self.track_table.rowCount()):
            item = self.track_table.item(row, 0)

            if item is not None:
                item.setCheckState(Qt.CheckState.Unchecked)
