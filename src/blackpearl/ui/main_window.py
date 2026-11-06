from PySide6.QtWidgets import QMainWindow, QLabel


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        
        self.setWindowTitle("BlackPearl")
        self.resize(900, 600)
        
        label = QLabel("BlackPearl — Universal Media Downloader")
        label.setStyleSheet("font-size: 20px;")
        
        self.setCentralWidget(label)
