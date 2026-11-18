import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from blackpearl.providers.base import (
    DownloadCancelled,
    DownloadOptions,
    MediaInfo,
    MediaProvider,
)
from blackpearl.services.download_manager import DownloadManager
from blackpearl.services.download_worker import DownloadJob


def wait_until(condition, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise AssertionError("Условие не выполнилось за отведённое время")
        QApplication.processEvents()
        time.sleep(0.01)


class ScriptedProvider(MediaProvider):
    """Поведение для каждой ссылки задаётся функцией в self.actions."""

    def __init__(self, actions=None) -> None:
        self.actions = actions or {}
        self.downloaded: list[str] = []

    def can_handle(self, url: str) -> bool:
        return True

    def get_info(self, url: str) -> MediaInfo:
        return MediaInfo(title=url, url=url, media_type="audio")

    def download(
        self,
        url,
        output_dir,
        options,
        progress_callback=None,
        cancel_event=None,
    ) -> None:
        self.downloaded.append(url)
        action = self.actions.get(url)
        if action is not None:
            action(progress_callback, cancel_event)
        elif progress_callback is not None:
            progress_callback(50.0)
            progress_callback(100.0)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def manager(app):
    manager = DownloadManager()
    manager.summaries = []
    manager.started = []
    manager.progress = []
    # Проверяем, что в момент finished поток уже освобождён.
    manager.busy_on_finish = []

    def on_finished(summary):
        manager.busy_on_finish.append(manager.is_busy)
        manager.summaries.append(summary)

    manager.finished.connect(on_finished)
    manager.track_started.connect(
        lambda index, total, title: manager.started.append((index, total, title))
    )
    manager.progress_changed.connect(manager.progress.append)
    yield manager
    manager.cancel()
    wait_until(lambda: not manager.is_busy)


def jobs(*names):
    return [DownloadJob(url=name, title=f"Title {name}") for name in names]


def run(manager, provider, job_list, tmp_path):
    manager.start(provider, job_list, tmp_path, DownloadOptions())
    wait_until(lambda: manager.summaries)
    return manager.summaries[0]


def test_queue_downloads_all_tracks_in_order(manager, tmp_path):
    provider = ScriptedProvider()

    summary = run(manager, provider, jobs("a", "b"), tmp_path)

    assert provider.downloaded == ["a", "b"]
    assert summary.total == 2
    assert summary.succeeded == 2
    assert summary.failed == ()
    assert not summary.cancelled
    assert manager.started == [(0, 2, "Title a"), (1, 2, "Title b")]
    assert manager.busy_on_finish == [False]


def test_overall_progress_spans_whole_queue(manager, tmp_path):
    run(manager, ScriptedProvider(), jobs("a", "b"), tmp_path)

    # Начало трека, 50% и 100% трека — в пересчёте на всю очередь.
    assert manager.progress == [0.0, 25.0, 50.0, 50.0, 75.0, 100.0, 100.0]


def test_failed_track_is_reported_and_queue_continues(manager, tmp_path):
    def fail(progress_callback, cancel_event):
        raise RuntimeError("нет доступа")

    provider = ScriptedProvider({"b": fail})

    summary = run(manager, provider, jobs("a", "b", "c"), tmp_path)

    assert provider.downloaded == ["a", "b", "c"]
    assert summary.succeeded == 2
    assert summary.failed == (("Title b", "нет доступа"),)
    assert not summary.cancelled


def test_error_without_message_uses_exception_name(manager, tmp_path):
    def fail(progress_callback, cancel_event):
        raise TimeoutError()

    summary = run(manager, ScriptedProvider({"a": fail}), jobs("a"), tmp_path)

    assert summary.failed == (("Title a", "TimeoutError"),)


def test_cancel_during_track_stops_queue(manager, tmp_path):
    def cancel_mid_track(progress_callback, cancel_event):
        manager.cancel()
        raise DownloadCancelled()

    provider = ScriptedProvider({"b": cancel_mid_track})

    summary = run(manager, provider, jobs("a", "b", "c"), tmp_path)

    assert provider.downloaded == ["a", "b"]
    assert summary.succeeded == 1
    assert summary.cancelled
    assert summary.failed == ()


def test_cancel_between_tracks_is_not_lost(manager, tmp_path):
    """Отмена сразу после окончания трека должна остановить очередь
    до начала следующего (раньше она терялась при смене потока)."""

    def finish_then_cancel(progress_callback, cancel_event):
        manager.cancel()  # Трек уже скачан, провайдер выходит штатно.

    provider = ScriptedProvider({"a": finish_then_cancel})

    summary = run(manager, provider, jobs("a", "b"), tmp_path)

    assert provider.downloaded == ["a"]
    assert summary.succeeded == 1
    assert summary.cancelled


def test_track_completed_despite_late_cancel_counts_as_success(manager, tmp_path):
    def finish_then_cancel(progress_callback, cancel_event):
        manager.cancel()

    summary = run(
        manager, ScriptedProvider({"a": finish_then_cancel}), jobs("a"), tmp_path
    )

    # Единственный трек скачан — это успех, а не отмена.
    assert summary.succeeded == 1
    assert not summary.cancelled


def test_start_while_busy_raises(manager, tmp_path):
    def wait_for_cancel(progress_callback, cancel_event):
        while not cancel_event.is_set():
            time.sleep(0.01)
        raise DownloadCancelled()

    manager.start(
        ScriptedProvider({"a": wait_for_cancel}),
        jobs("a"),
        tmp_path,
        DownloadOptions(),
    )

    with pytest.raises(RuntimeError, match="уже выполняется"):
        manager.start(ScriptedProvider(), jobs("b"), tmp_path, DownloadOptions())

    manager.cancel()
    wait_until(lambda: manager.summaries)
    assert manager.summaries[0].cancelled


def test_start_with_empty_queue_raises(manager, tmp_path):
    with pytest.raises(ValueError):
        manager.start(ScriptedProvider(), [], tmp_path, DownloadOptions())

    assert not manager.is_busy


def test_manager_can_run_queue_again_after_finish(manager, tmp_path):
    provider = ScriptedProvider()
    run(manager, provider, jobs("a"), tmp_path)

    manager.start(provider, jobs("b"), tmp_path, DownloadOptions())
    wait_until(lambda: len(manager.summaries) == 2)

    assert provider.downloaded == ["a", "b"]
    assert manager.summaries[1].succeeded == 1
