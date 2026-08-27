from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QTreeWidget, QTreeWidgetItem

from audio_bundle.core.models.node import NodeType
from audio_bundle.core.models.project import Project

ROLE_ID = Qt.ItemDataRole.UserRole
ROLE_KIND = Qt.ItemDataRole.UserRole + 1


class CourseTree(QTreeWidget):
    """Folder / block tree. Folders expand and collapse; they have no lock state."""

    selectionChangedId = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setColumnCount(1)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setUniformRowHeights(True)
        self.setAccessibleName("Course folders and blocks")
        self.setRootIsDecorated(True)
        self.setItemsExpandable(True)
        self.itemSelectionChanged.connect(self.selectionChangedId)

    def selected_id(self) -> str | None:
        item = self.currentItem()
        if item is None:
            return None
        return str(item.data(0, ROLE_ID))

    def selected_kind(self) -> str | None:
        item = self.currentItem()
        if item is None:
            return None
        return str(item.data(0, ROLE_KIND))

    def rebuild(self, project: Project, select_id: str | None = None) -> None:
        self.blockSignals(True)
        self.clear()
        self._fill(None, project, select_id)
        self.expandAll()
        self.blockSignals(False)
        if self.currentItem() is None and self.topLevelItemCount():
            self.setCurrentItem(self.topLevelItem(0))

    def _fill(self, parent_item: QTreeWidgetItem | None, project: Project, select_id: str | None) -> None:
        parent_id = None if parent_item is None else str(parent_item.data(0, ROLE_ID))
        for node in project.children(parent_id):
            if node.node_type is NodeType.FOLDER:
                label = f"📁  {node.name}"
                kind = str(NodeType.FOLDER)
            else:
                count = len(node.items)
                label = f"{node.name}    ({count} file{'s' if count != 1 else ''})"
                kind = str(NodeType.BLOCK)
            row = QTreeWidgetItem([label])
            row.setData(0, ROLE_ID, node.id)
            row.setData(0, ROLE_KIND, kind)
            row.setToolTip(0, node.name)
            if kind == str(NodeType.FOLDER):
                row.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicatorWhenChildless)
            else:
                row.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicator)
            if parent_item is None:
                self.addTopLevelItem(row)
            else:
                parent_item.addChild(row)
            if select_id == node.id:
                self.setCurrentItem(row)
            if kind == str(NodeType.FOLDER):
                self._fill(row, project, select_id)
