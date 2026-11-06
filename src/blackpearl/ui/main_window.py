from PySide6.QtCore import QThread, Slot
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from blackpearl.providers.registry import ProviderRegistry
from blackpearl.providers.yt_dlp_provider import YtDlpProvider
from blackpearl.services.info_worker import InfoWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("BlackPearl")
        self.resize(900, 600)

        self.registry = ProviderRegistry()
        self.registry.register(YtDlpProvider())
        
        self._info_thread: QThread | None = None
        self._info_worker: InfoWorker | None = None

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Вставь ссылку на медиа")

        self.check_button = QPushButton("Проверить источник")
        self.check_button.clicked.connect(self.check_url)

        self.status_label = QLabel("Ожидаю ссылку...")

        layout = QVBoxLayout()
        layout.addWidget(self.url_input)
        layout.addWidget(self.check_button)
        layout.addWidget(self.status_label)

        central_widget = QWidget()
        central_widget.setLayout(layout)

        self.setCentralWidget(central_widget)

    def check_url(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            self.status_label.setText("Введите ссылку")
            return

        provider = self.registry.get_provider(url)
        if provider is None:
            self.status_label.setText("Источник не поддерживается")
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

    @Slot(object)
    def show_info(self, info) -> None:
        self.status_label.setText(
            f"Название: {info.title}\n"
            f"Тип: {info.media_type}\n"
            f"Длительность: {info.duration_seconds}"
        )

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
