from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem

from audio_bundle.core.models.block import Block
from audio_bundle.core.models.media_item import MediaItem


class ReorderList(QListWidget):
    """Drag-and-drop list. After a drop, the widget order is the source of truth."""

    orderChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setAccessibleName("Reorderable list")

    def dropEvent(self, event) -> None:  # type: ignore[override]
        super().dropEvent(event)
        self.orderChanged.emit()

    def item_ids(self) -> list[str]:
        ids: list[str] = []
        for index in range(self.count()):
            row = self.item(index)
            if row is not None:
                ids.append(str(row.data(Qt.ItemDataRole.UserRole)))
        return ids


def file_item(item: MediaItem) -> QListWidgetItem:
    kind = "PDF" if str(item.media_type) == "pdf" else "Audio"
    row = QListWidgetItem(f"☰  {item.display_name}    ({kind})")
    row.setData(Qt.ItemDataRole.UserRole, item.id)
    row.setToolTip(item.original_filename)
    return row


def block_item(block: Block) -> QListWidgetItem:
    count = len(block.items)
    method = {
        "password": "password",
        "windows": "Windows",
        "none": "no password",
    }.get(str(block.auth_method), str(block.auth_method))
    label = f"☰  {block.name}    ({count} file{'s' if count != 1 else ''}, {method})"
    row = QListWidgetItem(label)
    row.setData(Qt.ItemDataRole.UserRole, block.id)
    return row
