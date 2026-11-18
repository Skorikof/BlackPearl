from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import IntEnum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
)


class Column(IntEnum):
    CHECK = 0
    ARTIST = 1
    TITLE = 2
    DURATION = 3


HEADERS = {
    Column.CHECK: "",
    Column.ARTIST: "Исполнитель",
    Column.TITLE: "Название",
    Column.DURATION: "Длительность",
}

CHECK_COLUMN_WIDTH = 40


@dataclass(frozen=True)
class TableRow:
    """Данные одной строки таблицы."""

    artist: str
    title: str
    duration_seconds: float | None = None
    checked: bool = True


def format_duration(seconds: float | None) -> str:
    """Форматирует длительность: «3:07» или «1:02:03» для длинных записей."""
    if seconds is None:
        return ""
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


class AudioTable:
    """Обёртка над QTableWidget из формы: строки с галочкой выбора,
    исполнителем, названием и длительностью."""

    def __init__(self, table: QTableWidget) -> None:
        self._table = table
        self._configure()

    def _configure(self) -> None:
        table = self._table
        table.setColumnCount(len(Column))
        table.setHorizontalHeaderLabels([HEADERS[column] for column in Column])
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        header = table.horizontalHeader()
        # Галочка — узкая фиксированная колонка, длительность — по содержимому,
        # оставшееся место делят исполнитель и название.
        header.setSectionResizeMode(Column.CHECK, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(Column.ARTIST, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(Column.TITLE, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(
            Column.DURATION, QHeaderView.ResizeMode.ResizeToContents
        )
        table.setColumnWidth(Column.CHECK, CHECK_COLUMN_WIDTH)

    def row_count(self) -> int:
        return self._table.rowCount()

    def clear(self) -> None:
        self._table.setRowCount(0)

    def set_rows(self, rows: Iterable[TableRow]) -> None:
        """Заменяет содержимое таблицы одним пакетом, без itemChanged."""
        rows = list(rows)
        with self._batch_update():
            self._table.setRowCount(len(rows))
            for index, row in enumerate(rows):
                self._fill_row(index, row)

    def _fill_row(self, index: int, row: TableRow) -> None:
        checkbox = QTableWidgetItem()
        checkbox.setFlags(
            Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
        )
        checkbox.setCheckState(_check_state(row.checked))

        duration = QTableWidgetItem(format_duration(row.duration_seconds))
        duration.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        self._table.setItem(index, Column.CHECK, checkbox)
        self._table.setItem(index, Column.ARTIST, _text_item(row.artist))
        self._table.setItem(index, Column.TITLE, _text_item(row.title))
        self._table.setItem(index, Column.DURATION, duration)

    def is_checked(self, row: int) -> bool:
        item = self._table.item(row, Column.CHECK)
        return item is not None and item.checkState() == Qt.CheckState.Checked

    def set_checked(self, row: int, checked: bool) -> None:
        """Меняет галочку одной строки (с сигналом itemChanged, как при клике)."""
        item = self._table.item(row, Column.CHECK)
        if item is not None:
            item.setCheckState(_check_state(checked))

    def set_all_checked(self, checked: bool) -> None:
        """Меняет все галочки одним пакетом, без itemChanged."""
        state = _check_state(checked)
        with self._batch_update():
            for row in range(self._table.rowCount()):
                item = self._table.item(row, Column.CHECK)
                if item is not None:
                    item.setCheckState(state)

    def checked_rows(self) -> list[int]:
        return [row for row in range(self._table.rowCount()) if self.is_checked(row)]

    def has_checked(self) -> bool:
        return any(self.is_checked(row) for row in range(self._table.rowCount()))

    def row_title(self, row: int) -> str:
        """Название строки в виде «Исполнитель — Название»."""
        artist = self._text(row, Column.ARTIST)
        title = self._text(row, Column.TITLE)
        return f"{artist} — {title}" if artist else title

    def _text(self, row: int, column: Column) -> str:
        item = self._table.item(row, column)
        return item.text() if item is not None else ""

    @contextmanager
    def _batch_update(self) -> Iterator[None]:
        """Массовое изменение без сигнала itemChanged на каждую ячейку.

        Иначе каждая ячейка вызывала бы пересчёт кнопок в окне —
        квадратичная сложность на больших коллекциях. Вызывающий код
        после массового изменения сам один раз обновляет кнопки.
        """
        was_blocked = self._table.blockSignals(True)
        self._table.setUpdatesEnabled(False)
        try:
            yield
        finally:
            self._table.setUpdatesEnabled(True)
            self._table.blockSignals(was_blocked)


def _check_state(checked: bool) -> Qt.CheckState:
    return Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked


def _text_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    # Длинные названия обрезаются колонкой — полный текст в подсказке.
    item.setToolTip(text)
    return item
