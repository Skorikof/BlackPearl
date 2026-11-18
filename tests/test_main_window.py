import os
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from blackpearl.providers.base import (
    CollectionProvider,
    DownloadCancelled,
    MediaInfo,
    MediaProvider,
    TrackEntry,
)
from blackpearl.providers.registry import ProviderRegistry
from blackpearl.ui import view
from blackpearl.services.download_worker import DownloadSummary
from blackpearl.ui.view import MainWindow
from blackpearl.ui.widgets.audio_table import TableRow

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
                raise DownloadCancelled()
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
    window._table.set_rows([TableRow(artist="", title="Media")])
    window.start_download()
    wait_until(lambda: provider.calls == 1)


def test_check_url_is_blocked_during_download(window, provider):
    start_single_download(window, provider)

    assert not window.ui.audio_check_btn.isEnabled()

    window.ui.audio_url_le.setText("https://example.com/other")
    window.check_url()

    # Проверка ссылки не должна сбрасывать таблицу и текущего провайдера.
    assert window._current_provider is provider
    assert window._table.row_count() == 1

    provider.release.set()
    wait_until(lambda: "Загрузка завершена" in window.ui.audio_label.text())

    assert window.ui.audio_check_btn.isEnabled()
    assert not window.ui.audio_cancel_btn.isEnabled()


def test_check_button_reenabled_after_cancel(window, provider):
    start_single_download(window, provider)

    window.download_manager.cancel()
    wait_until(lambda: not window.download_manager.is_busy)

    assert window.ui.audio_label.text() == "Загрузка отменена. Скачано 0 из 1"
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

    window._table.set_checked(2, True)

    assert window.ui.audio_download_btn.isEnabled()


class FakeCollectionProvider(FlakyProvider, CollectionProvider):
    """Провайдер коллекций без привязки к Яндексу."""

    def __init__(self) -> None:
        super().__init__()
        self.collection_requests = []

    def is_collection(self, url: str) -> bool:
        return "/album/" in url

    def get_collection_tracks(self, url: str):
        self.collection_requests.append(url)
        return make_tracks(3)


def use_only(window: MainWindow, provider: MediaProvider) -> None:
    window.registry = ProviderRegistry()
    window.registry.register(provider)


def test_check_url_loads_collection_from_any_collection_provider(window):
    provider = FakeCollectionProvider()
    use_only(window, provider)
    window.ui.audio_url_le.setText("https://example.com/album/1")

    window.check_url()
    assert not window.ui.audio_check_btn.isEnabled()
    wait_until(lambda: window.ui.audio_check_btn.isEnabled())

    assert provider.collection_requests == ["https://example.com/album/1"]
    assert window._table.row_count() == 3
    assert window.ui.audio_label.text() == "Найдено треков: 3"


def test_check_url_gets_info_for_single_media(window):
    provider = FakeCollectionProvider()
    use_only(window, provider)
    window.ui.audio_url_le.setText("https://example.com/track/1")

    window.check_url()
    wait_until(lambda: window.ui.audio_check_btn.isEnabled())

    assert provider.collection_requests == []
    assert window._table.row_count() == 1
    assert window.ui.audio_label.text() == "Найдено: Media"


def test_check_url_shows_lookup_error(window):
    class BrokenProvider(FlakyProvider):
        def get_info(self, url):
            raise RuntimeError("видео недоступно")

    use_only(window, BrokenProvider())
    window.ui.audio_url_le.setText("https://example.com/video")

    window.check_url()
    wait_until(lambda: window.ui.audio_check_btn.isEnabled())

    assert window.ui.audio_label.text() == (
        "Не удалось получить информацию: видео недоступно"
    )
    assert window._table.row_count() == 0


def test_close_during_lookup_waits_for_it(window):
    release = threading.Event()

    class SlowProvider(FlakyProvider):
        def get_info(self, url):
            release.wait(5)
            return super().get_info(url)

    use_only(window, SlowProvider())
    window.ui.audio_url_le.setText("https://example.com/video")
    window.check_url()

    window.close()
    assert window.isVisible()

    release.set()
    wait_until(lambda: not window.isVisible())
    assert not window._lookup.is_running


@pytest.mark.parametrize(
    ("summary", "expected"),
    [
        (DownloadSummary(total=3, succeeded=3), "Загрузка завершена. Скачано треков: 3"),
        (
            DownloadSummary(total=3, succeeded=1, skipped=2),
            "Загрузка завершена. Скачано 1 из 3, уже были: 2",
        ),
        (
            DownloadSummary(total=4, succeeded=1, skipped=2, failed=(("x", "e"),)),
            "Загрузка завершена. Скачано 1 из 4, уже были: 2, ошибок: 1",
        ),
        (
            DownloadSummary(total=5, succeeded=1, skipped=1, cancelled=True),
            "Загрузка отменена. Скачано 1 из 5, уже были: 1",
        ),
    ],
)
def test_summary_text(summary, expected):
    assert MainWindow._summary_text(summary) == expected
