import yt_dlp
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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("BlackPearl")
        self.resize(900, 600)

        self.registry = ProviderRegistry()
        self.registry.register(YtDlpProvider())

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

        self.status_label.setText("Получаю информацию...")
        try:
            info = provider.get_info(url)

        except yt_dlp.utils.DownloadError as error:
            self.status_label.setText(
                f"Не удалось получить информацию: {error}"
            )
            return

        self.status_label.setText(
            f"Название: {info.title}\n"
            f"Тип: {info.media_type}\n"
            f"Длительность: {info.duration_seconds}"
        )
