import os
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from blackpearl.providers.base import MediaInfo, MediaProvider
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
        audio_bitrate_kbps=None,
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
def window(app, provider, monkeypatch, tmp_path):
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
