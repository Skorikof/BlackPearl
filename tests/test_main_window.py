import os
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from blackpearl.providers.base import MediaInfo, MediaProvider, TrackEntry
from blackpearl.ui import view
from blackpearl.ui.view import MainWindow

URL = "https://example.com/media"


class BlockingProvider(MediaProvider):
    """Провайдер, загрузка которого висит, пока её не отпустят или не отменят."""

    def __init__(self) -> None:
        self.release = threading.Event()
        self.calls = 0

    def can_handle(self, url: str) -> bool:
        return True

    def get_info(self, url: str) -> MediaInfo:
        return MediaInfo(title="Media", url=url, media_type="audio")

    def download(
        self,
        url,
        output_dir,
        options=None,
        progress_callback=None,
        cancel_event=None,
    ) -> None:
        self.calls += 1
        while not self.release.is_set():
            if cancel_event is not None and cancel_event.is_set():
                return
            time.sleep(0.01)


def wait_until(condition, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise AssertionError("Условие не выполнилось за отведённое время")
        QApplication.processEvents()
        time.sleep(0.01)


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    application.setQuitOnLastWindowClosed(False)
    return application


@pytest.fixture
def provider():
    return BlockingProvider()


@pytest.fixture
def warnings(monkeypatch):
    """Перехватывает QMessageBox.warning, чтобы модальное окно не блокировало тест."""
    calls = []
    monkeypatch.setattr(
        view.QMessageBox,
        "warning",
        staticmethod(lambda parent, title, text: calls.append((title, text))),
    )
    return calls


@pytest.fixture
def window(app, provider, warnings, monkeypatch, tmp_path):
    monkeypatch.setattr(
        view.QFileDialog,
        "getExistingDirectory",
        staticmethod(lambda *args, **kwargs: str(tmp_path)),
    )
    main_window = MainWindow()
    main_window.show()
    yield main_window
    provider.release.set()
    wait_until(lambda: not main_window._has_running_threads())
    main_window.deleteLater()
    QApplication.processEvents()


def start_single_download(window: MainWindow, provider: MediaProvider) -> None:
    window._current_provider = provider
    window._current_url = URL
    window._table_entries = [URL]
    window._table.set_row_count(1)
    window._table.add_table_row(0, "", "Media", None)
    window.start_download()
    wait_until(lambda: provider.calls == 1)


def test_check_url_is_blocked_during_download(window, provider):
    start_single_download(window, provider)

    assert not window.ui.audio_check_btn.isEnabled()

    window.ui.audio_url_le.setText("https://example.com/other")
    window.check_url()

    # Проверка ссылки не должна сбрасывать таблицу и провайдера очереди.
    assert window._download_provider is provider
    assert window._current_provider is provider
    assert window._table.get_row_count() == 1

    provider.release.set()
    wait_until(lambda: "Загрузка завершена" in window.ui.audio_label.text())

    assert window.ui.audio_check_btn.isEnabled()
    assert not window.ui.audio_cancel_btn.isEnabled()


def test_check_button_reenabled_after_cancel(window, provider):
    start_single_download(window, provider)

    window.download_manager.cancel_download()
    wait_until(lambda: not window.download_manager.is_busy)

    assert window.ui.audio_label.text() == "Загрузка отменена"
    assert window.ui.audio_check_btn.isEnabled()


def test_close_while_idle_closes_immediately(window):
    window.close()

    assert not window.isVisible()


def test_close_during_download_waits_for_thread(window, provider):
    start_single_download(window, provider)

    window.close()

    # Окно не закрывается, пока поток загрузки работает,
    # но загрузка отменяется.
    assert window.isVisible()
    assert window._closing

    wait_until(lambda: not window.isVisible())
    assert not window.download_manager.is_busy


class FlakyProvider(BlockingProvider):
    """Мгновенно «скачивает» всё, кроме ссылок, содержащих 'bad'."""

    def download(self, url, output_dir, options=None, **kwargs) -> None:
        self.calls += 1
        if "bad" in url:
            raise RuntimeError(f"нет доступа к {url}")


def make_tracks(count: int, bad: set[int] = frozenset()):
    return [
        TrackEntry(
            track_id=str(i),
            album_id="1",
            title=f"Track {i}",
            artists="Artist",
            duration_seconds=60.0,
            url=f"https://example.com/{'bad' if i in bad else 'ok'}/{i}",
        )
        for i in range(count)
    ]


def test_failed_track_does_not_stop_queue(window, warnings):
    flaky = FlakyProvider()
    window._current_provider = flaky
    window.show_collection(make_tracks(3, bad={1}))

    window.start_download()
    wait_until(lambda: "Загрузка завершена" in window.ui.audio_label.text())

    assert flaky.calls == 3
    assert window.ui.audio_label.text() == (
        "Загрузка завершена. Скачано 2 из 3, ошибок: 1"
    )
    assert window.ui.audio_check_btn.isEnabled()
    assert len(warnings) == 1
    _, text = warnings[0]
    assert "Artist — Track 1" in text
    assert "нет доступа" in text
    assert "Track 0" not in text


def test_no_warning_when_all_tracks_downloaded(window, warnings):
    flaky = FlakyProvider()
    window._current_provider = flaky
    window.show_collection(make_tracks(2))

    window.start_download()
    wait_until(lambda: "Загрузка завершена" in window.ui.audio_label.text())

    assert window.ui.audio_label.text() == (
        "Загрузка завершена. Скачано треков: 2"
    )
    assert warnings == []


def test_failure_report_is_truncated(window, warnings):
    failed = [(f"Track {i}", "ошибка") for i in range(20)]

    window._report_failures(failed)

    _, text = warnings[0]
    assert "Track 14" in text
    assert "Track 15" not in text
    assert "…и ещё 5" in text


def test_bulk_table_changes_do_not_emit_item_changed(window):
    emitted = []
    window.ui.audio_tableWidget.itemChanged.connect(
        lambda item: emitted.append(item)
    )

    window.show_collection(make_tracks(50))
    window.select_no_tracks()
    window.select_all_tracks()

    assert emitted == []
    # Кнопки всё равно пересчитаны после массовых операций.
    assert window.ui.audio_download_btn.isEnabled()

    window.select_no_tracks()
    assert not window.ui.audio_download_btn.isEnabled()


def test_manual_check_still_updates_buttons(window):
    window.show_collection(make_tracks(3))
    window.select_no_tracks()
    assert not window.ui.audio_download_btn.isEnabled()

    window._table.get_item(2, 0).setCheckState(Qt.CheckState.Checked)

    assert window.ui.audio_download_btn.isEnabled()
