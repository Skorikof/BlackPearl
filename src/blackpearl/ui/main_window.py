from pathlib import Path

from PySide6.QtCore import QThread, Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from blackpearl.providers.registry import ProviderRegistry
from blackpearl.providers.yandex_music_provider import YandexMusicProvider
from blackpearl.providers.yt_dlp_provider import YtDlpProvider
from blackpearl.services.download_manager import DownloadManager
from blackpearl.services.info_worker import InfoWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("BlackPearl")
        self.resize(900, 600)

        self.registry = ProviderRegistry()
        self.registry.register(YandexMusicProvider())
        self.registry.register(YtDlpProvider())
        
        self._info_thread: QThread | None = None
        self._info_worker: InfoWorker | None = None

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

        layout = QVBoxLayout()
        layout.addWidget(self.url_input)
        layout.addWidget(self.check_button)

        download_buttons = QHBoxLayout()
        download_buttons.addWidget(self.download_button)
        download_buttons.addWidget(self.cancel_button)

        layout.addLayout(download_buttons)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)

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

    @Slot(object)
    def show_info(self, info) -> None:
        self.status_label.setText(
            f"Название: {info.title}\n"
            f"Тип: {info.media_type}\n"
            f"Длительность: {info.duration_seconds}"
        )
        self.download_button.setEnabled(True)

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

        self.download_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress_bar.setValue(0)

        self.status_label.setText("Загрузка началась...")

        try:
            self.download_manager.start_download(
                provider=self._current_provider,
                url=self._current_url,
                output_dir=Path(output_dir),
            )

        except RuntimeError as error:
            self.status_label.setText(str(error))
            self.download_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            
    @Slot(float)
    def update_progress(self, percent: float) -> None:
        self.progress_bar.setValue(round(percent))
        
    @Slot()
    def download_completed(self) -> None:
        self.progress_bar.setValue(100)
        self.status_label.setText("Загрузка завершена")
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