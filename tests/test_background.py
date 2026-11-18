import os
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication

from blackpearl.services.background import BackgroundTask


def wait_until(condition, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise AssertionError("Условие не выполнилось за отведённое время")
        QApplication.processEvents()
        time.sleep(0.01)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def task(app):
    task = BackgroundTask()
    task.events = []
    task.finished.connect(
        lambda: task.events.append(("finished", task.is_running))
    )
    yield task
    wait_until(lambda: not task.is_running)


def test_result_is_delivered_in_main_thread(app, task):
    worker_threads = []

    def work():
        worker_threads.append(QThread.currentThread())
        return 42

    def on_success(result):
        task.events.append(("success", result, QThread.currentThread()))

    task.start(work, on_success=on_success)
    wait_until(lambda: ("finished", False) in task.events)

    assert worker_threads[0] is not app.thread()
    assert task.events == [
        ("success", 42, app.thread()),
        ("finished", False),
    ]


def test_error_message_is_delivered(task):
    def work():
        raise ValueError("плохая ссылка")

    task.start(
        work,
        on_success=lambda result: task.events.append(("success", result)),
        on_error=lambda message: task.events.append(("error", message)),
    )
    wait_until(lambda: ("finished", False) in task.events)

    assert task.events == [("error", "плохая ссылка"), ("finished", False)]


def test_error_without_message_uses_exception_name(task):
    def work():
        raise TimeoutError()

    task.start(
        work,
        on_success=lambda result: None,
        on_error=lambda message: task.events.append(("error", message)),
    )
    wait_until(lambda: ("finished", False) in task.events)

    assert ("error", "TimeoutError") in task.events


def test_error_without_handler_still_finishes(task):
    def work():
        raise RuntimeError("boom")

    task.start(work, on_success=lambda result: None)
    wait_until(lambda: ("finished", False) in task.events)


def test_start_while_running_raises(task):
    release = threading.Event()

    task.start(lambda: release.wait(5), on_success=lambda result: None)
    assert task.is_running

    with pytest.raises(RuntimeError, match="уже выполняется"):
        task.start(lambda: None, on_success=lambda result: None)

    release.set()
    wait_until(lambda: not task.is_running)


def test_task_can_be_reused(task):
    results = []

    task.start(lambda: "first", on_success=results.append)
    wait_until(lambda: not task.is_running)
    task.start(lambda: "second", on_success=results.append)
    wait_until(lambda: not task.is_running)

    assert results == ["first", "second"]
