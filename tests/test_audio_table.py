import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QHeaderView, QTableWidget

from blackpearl.ui.widgets.audio_table import (
    CHECK_COLUMN_WIDTH,
    AudioTable,
    Column,
    TableRow,
    format_duration,
)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def widget(app):
    widget = QTableWidget()
    yield widget
    widget.deleteLater()


@pytest.fixture
def table(widget):
    return AudioTable(widget)


ROWS = [
    TableRow("Artist A", "First", 187),
    TableRow("", "Second", None, checked=False),
    TableRow("Artist C", "Third", 3723),
]


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (None, ""),
        (0, "0:00"),
        (7, "0:07"),
        (187.9, "3:07"),
        (3599, "59:59"),
        (3600, "1:00:00"),
        (3723, "1:02:03"),
    ],
)
def test_format_duration(seconds, expected):
    assert format_duration(seconds) == expected


def test_columns_and_headers(widget, table):
    assert widget.columnCount() == 4
    labels = [
        widget.horizontalHeaderItem(column).text() for column in Column
    ]
    assert labels == ["", "Исполнитель", "Название", "Длительность"]


def test_check_column_is_narrow_and_fixed(widget, table):
    header = widget.horizontalHeader()

    assert header.sectionResizeMode(Column.CHECK) == QHeaderView.ResizeMode.Fixed
    assert widget.columnWidth(Column.CHECK) == CHECK_COLUMN_WIDTH
    assert header.sectionResizeMode(Column.TITLE) == QHeaderView.ResizeMode.Stretch


def test_set_rows_fills_table(widget, table):
    table.set_rows(ROWS)

    assert table.row_count() == 3
    assert widget.item(0, Column.ARTIST).text() == "Artist A"
    assert widget.item(0, Column.TITLE).toolTip() == "First"
    assert widget.item(0, Column.DURATION).text() == "3:07"
    assert widget.item(1, Column.DURATION).text() == ""
    assert widget.item(2, Column.DURATION).text() == "1:02:03"


def test_set_rows_replaces_previous_content(table):
    table.set_rows(ROWS)
    table.set_rows([TableRow("X", "Only")])

    assert table.row_count() == 1
    assert table.row_title(0) == "X — Only"


def test_set_rows_accepts_generator(table):
    table.set_rows(TableRow("A", f"T{i}") for i in range(5))

    assert table.row_count() == 5


def test_checked_state(table):
    table.set_rows(ROWS)

    assert table.checked_rows() == [0, 2]
    assert table.has_checked()
    assert table.is_checked(0)
    assert not table.is_checked(1)


def test_set_all_checked(table):
    table.set_rows(ROWS)

    table.set_all_checked(False)
    assert table.checked_rows() == []
    assert not table.has_checked()

    table.set_all_checked(True)
    assert table.checked_rows() == [0, 1, 2]


def test_bulk_operations_do_not_emit_item_changed(widget, table):
    emitted = []
    widget.itemChanged.connect(emitted.append)

    table.set_rows(ROWS)
    table.set_all_checked(False)
    table.set_all_checked(True)

    assert emitted == []
    # Сигналы таблицы снова включены после массовых операций.
    assert not widget.signalsBlocked()
    assert widget.updatesEnabled()


def test_set_checked_emits_item_changed_like_a_click(widget, table):
    table.set_rows(ROWS)
    emitted = []
    widget.itemChanged.connect(emitted.append)

    table.set_checked(1, True)

    assert table.is_checked(1)
    assert len(emitted) == 1


def test_row_title_with_and_without_artist(table):
    table.set_rows(ROWS)

    assert table.row_title(0) == "Artist A — First"
    assert table.row_title(1) == "Second"


def test_clear(table):
    table.set_rows(ROWS)
    table.clear()

    assert table.row_count() == 0
    assert not table.has_checked()
