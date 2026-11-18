from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
)

from blackpearl.providers.base import (
    CollectionProvider,
    DownloadOptions,
    TrackEntry,
)
from blackpearl.providers.registry import ProviderRegistry
from blackpearl.providers.yandex_music_provider import YandexMusicProvider
from blackpearl.providers.yt_dlp_provider import YtDlpProvider
from blackpearl.services.background import BackgroundTask
from blackpearl.services.download_manager import DownloadManager
from blackpearl.services.download_worker import DownloadJob, DownloadSummary
from blackpearl.ui.ui_py.main_ui import Ui_MainWindow
from blackpearl.ui.widgets.audio_table import AudioTable, TableRow


LOSSLESS = "lossless"


class MainWindow(QMainWindow):
    # Сколько ошибок показывать в итоговом окне, остальные — числом.
    MAX_REPORTED_FAILURES = 15

    def __init__(self) -> None:
        super().__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Проверка ссылки: информация о медиа или список треков коллекции.
        self._lookup = BackgroundTask(self)
        self._table = AudioTable(self.ui.audio_tableWidget)

        self._current_provider = None
        self._current_url = ""
        self._table_entries: list[TrackEntry | str] = []

        self._closing = False

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
        # Пункт добавляется кодом, пока его нет в форме Designer.
        if self.ui.audio_quality_cb.findData(LOSSLESS) < 0:
            self.ui.audio_quality_cb.addItem("FLAC (lossless)", LOSSLESS)

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
        self.ui.audio_cancel_btn.clicked.connect(self.download_manager.cancel)
        self.ui.audio_check_all_btn.clicked.connect(self.select_all_tracks)
        self.ui.audio_remove_all_btn.clicked.connect(self.select_no_tracks)
        self.ui.audio_tableWidget.itemChanged.connect(
            self._update_table_controls
        )

        self.download_manager.track_started.connect(self._on_track_started)
        self.download_manager.progress_changed.connect(self.update_progress)
        self.download_manager.finished.connect(self._on_download_finished)
        self._lookup.finished.connect(self._on_lookup_finished)

    def _set_status(self, message: str) -> None:
        self.ui.audio_label.setText(message)

    def _clear_table(self) -> None:
        self._table_entries.clear()
        self._table.clear()
        self._update_table_controls()

    def _update_table_controls(self) -> None:
        has_rows = self._table.row_count() > 0
        self.ui.audio_check_all_btn.setEnabled(has_rows)
        self.ui.audio_remove_all_btn.setEnabled(has_rows)
        self.ui.audio_download_btn.setEnabled(self._table.has_checked())

    def _set_downloading(self, downloading: bool) -> None:
        """Переключает кнопки между режимом загрузки и ожидания."""
        self.ui.audio_download_btn.setEnabled(not downloading)
        self.ui.audio_cancel_btn.setEnabled(downloading)
        self.ui.audio_check_btn.setEnabled(not downloading)

    @staticmethod
    def _entry_url(entry: TrackEntry | str) -> str:
        return entry if isinstance(entry, str) else entry.url

    def _has_running_threads(self) -> bool:
        return (
            self._lookup.is_running
            or self.download_manager.is_busy
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._has_running_threads():
            super().closeEvent(event)
            return

        # Нельзя уничтожать QThread, пока он работает: отменяем загрузку
        # и закрываем окно, когда все фоновые потоки завершатся.
        event.ignore()
        if self._closing:
            return
        self._closing = True
        self.download_manager.cancel()
        self.ui.centralwidget.setEnabled(False)
        self._set_status("Завершаю фоновые операции...")

    def _close_if_pending(self) -> None:
        if self._closing and not self._has_running_threads():
            self.close()

    def check_url(self) -> None:
        if self.download_manager.is_busy:
            self._set_status("Дождитесь окончания загрузки или отмените её")
            return

        self._clear_table()
        self._current_provider = None
        self._current_url = ""

        url = self.ui.audio_url_le.text().strip()
        if not url:
            self._set_status("Введите ссылку")
            return

        provider = self.registry.get_provider(url, kind="audio")
        if provider is None:
            self._set_status("Источник не поддерживается")
            return

        self._current_provider = provider
        self._current_url = url
        self.ui.audio_check_btn.setEnabled(False)

        if (
            isinstance(provider, CollectionProvider)
            and provider.is_collection(url)
        ):
            self._set_status("Получаю список треков...")
            self._lookup.start(
                lambda: provider.get_collection_tracks(url),
                on_success=self.show_collection,
                on_error=self.show_error,
            )
        else:
            self._set_status("Получаю информацию...")
            self._lookup.start(
                lambda: provider.get_info(url),
                on_success=self.show_info,
                on_error=self.show_error,
            )

    @Slot(object)
    def show_info(self, info) -> None:
        self._table_entries = [self._current_url]
        self._table.set_rows(
            [TableRow(artist="", title=info.title,
                      duration_seconds=info.duration_seconds)]
        )
        self._update_table_controls()
        self._set_status(f"Найдено: {info.title}")

    @Slot(str)
    def show_error(self, message: str) -> None:
        self._clear_table()
        self._set_status(f"Не удалось получить информацию: {message}")

    @Slot()
    def _on_lookup_finished(self) -> None:
        self.ui.audio_check_btn.setEnabled(True)
        self._close_if_pending()

    @Slot(object)
    def show_collection(self, tracks: list[TrackEntry]) -> None:
        self._table_entries = list(tracks)
        self._table.set_rows(
            TableRow(
                artist=track.artists,
                title=track.title,
                duration_seconds=track.duration_seconds,
            )
            for track in tracks
        )
        self._update_table_controls()
        self._set_status(f"Найдено треков: {len(tracks)}")

    def select_all_tracks(self) -> None:
        self._table.set_all_checked(True)
        self._update_table_controls()

    def select_no_tracks(self) -> None:
        self._table.set_all_checked(False)
        self._update_table_controls()

    def start_download(self) -> None:
        if self._current_provider is None or not self._table_entries:
            return
        if self.download_manager.is_busy:
            return

        jobs = [
            DownloadJob(
                url=self._entry_url(self._table_entries[row]),
                title=self._table.row_title(row),
            )
            for row in self._table.checked_rows()
        ]
        if not jobs:
            self._set_status("Выбери хотя бы один трек")
            return

        output_dir = QFileDialog.getExistingDirectory(
            self,
            "Выбери папку для сохранения музыки",
        )
        if not output_dir:
            return

        # Менеджер получает провайдера при старте и держит его до конца
        # очереди, поэтому новая проверка ссылки не может его подменить.
        self.download_manager.start(
            provider=self._current_provider,
            jobs=jobs,
            output_dir=Path(output_dir),
            options=self._audio_options(),
        )
        self.ui.audio_progressBar.setValue(0)
        self._set_downloading(True)

    def _audio_options(self) -> DownloadOptions:
        quality = self.ui.audio_quality_cb.currentData()
        if quality == LOSSLESS:
            # Источники без lossless (yt-dlp) скачают MP3 в максимальном
            # качестве.
            return DownloadOptions(
                kind="audio", lossless=True, audio_bitrate_kbps=320
            )
        return DownloadOptions(kind="audio", audio_bitrate_kbps=quality)

    @Slot(int, int, str)
    def _on_track_started(self, index: int, total: int, title: str) -> None:
        self._set_status(f"Скачивание {index + 1} из {total}: {title}")

    @Slot(float)
    def update_progress(self, percent: float) -> None:
        self.ui.audio_progressBar.setValue(round(percent))

    @Slot(object)
    def _on_download_finished(self, summary: DownloadSummary) -> None:
        if self._closing:
            self._close_if_pending()
            return

        self._set_downloading(False)
        self._set_status(self._summary_text(summary))
        if summary.failed:
            self._report_failures(list(summary.failed))

    @staticmethod
    def _summary_text(summary: DownloadSummary) -> str:
        if summary.cancelled:
            text = (
                f"Загрузка отменена. Скачано {summary.succeeded} "
                f"из {summary.total}"
            )
        elif not summary.failed and not summary.skipped:
            return f"Загрузка завершена. Скачано треков: {summary.total}"
        else:
            text = (
                f"Загрузка завершена. Скачано {summary.succeeded} "
                f"из {summary.total}"
            )
        if summary.skipped:
            text += f", уже были: {summary.skipped}"
        if summary.failed:
            text += f", ошибок: {len(summary.failed)}"
        return text

    def _report_failures(self, failed: list[tuple[str, str]]) -> None:
        lines = [f"• {title}: {message}" for title, message in failed]
        if len(lines) > self.MAX_REPORTED_FAILURES:
            hidden = len(lines) - self.MAX_REPORTED_FAILURES
            lines = lines[: self.MAX_REPORTED_FAILURES]
            lines.append(f"…и ещё {hidden}")
        QMessageBox.warning(
            self,
            "Не все треки скачаны",
            "Не удалось скачать:\n\n" + "\n".join(lines),
        )
