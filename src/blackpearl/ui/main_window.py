from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QPushButton,
    QLabel,
)

from blackpearl.providers.demo import DemoProvider
from blackpearl.providers.registry import ProviderRegistry


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("BlackPearl")
        self.resize(900, 600)

        self.registry = ProviderRegistry()
        self.registry.register(DemoProvider())

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

        info = provider.get_info(url)

        self.status_label.setText(
            f"Источник найден: {info.title}"
        )
