from collections.abc import Iterator
from contextlib import contextmanager

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem
    )


class AudioTable():
    def __init__(self, table: QTableWidget):
        super().__init__()
        self._table = table
        self._create()
        
    def _create(self):
        self._table.setColumnCount(4)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._table.setColumnWidth(0, 40)
    
    def set_table_widget(self, table: QTableWidget) -> None:
        self._table = table
        
    def set_row_count(self, value: int) -> None:
        self._table.setRowCount(value)
        
    def get_have_row(self) -> bool:
        return self._table.rowCount() > 0
        
    def get_row_count(self) -> int:
        return self._table.rowCount()
    
    def set_add_table_row(self, row, checkbox, artist, title, duration):
        self._table.setItem(row, 0, checkbox)
        self._table.setItem(row, 1, QTableWidgetItem(artist))
        self._table.setItem(row, 2, QTableWidgetItem(title))
        self._table.setItem(row, 3, QTableWidgetItem(duration))
    
    def get_item(self, r, c):
        return self._table.item(r, c)

    @contextmanager
    def batch_update(self) -> Iterator[None]:
        """Массовое изменение таблицы без сигнала itemChanged на каждую ячейку.

        После выхода из блока вызывающий код должен сам один раз
        обновить зависящие от таблицы элементы интерфейса.
        """
        was_blocked = self._table.blockSignals(True)
        self._table.setUpdatesEnabled(False)
        try:
            yield
        finally:
            self._table.setUpdatesEnabled(True)
            self._table.blockSignals(was_blocked)

    def set_all_checked(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        with self.batch_update():
            for row in range(self._table.rowCount()):
                item = self._table.item(row, 0)
                if item is not None:
                    item.setCheckState(state)

    def is_checked(self, row: int) -> bool:
        item = self._table.item(row, 0)
        return item is not None and item.checkState() == Qt.CheckState.Checked

    def row_title(self, row: int) -> str:
        """Название строки в виде «Исполнитель — Название»."""
        artist_item = self._table.item(row, 1)
        title_item = self._table.item(row, 2)
        artist = artist_item.text() if artist_item is not None else ""
        title = title_item.text() if title_item is not None else ""
        return f"{artist} — {title}" if artist else title

    def update_table_controls(self):
        flag_all = self._table.rowCount() > 0
        has_selected = any(
            self.is_checked(row) for row in range(self._table.rowCount())
        )
        return flag_all, has_selected

    def add_table_row(self,
                        row: int,
                        artist: str,
                        title: str,
                        duration_seconds: float | None,
                        checked: bool = True,
                        ) -> None:
        checkbox = QTableWidgetItem()
        checkbox.setFlags(
            Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
        )
        checkbox.setCheckState(
            Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        )

        duration = ""
        if duration_seconds is not None:
            minutes, seconds = divmod(int(duration_seconds), 60)
            duration = f"{minutes}:{seconds:02d}"
            
        self._table.setItem(row, 0, checkbox)
        self._table.setItem(row, 1, QTableWidgetItem(artist))
        self._table.setItem(row, 2, QTableWidgetItem(title))
        self._table.setItem(row, 3, QTableWidgetItem(duration))
