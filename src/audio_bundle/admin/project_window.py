from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from audio_bundle.admin.block_editor import BlockEditor
from audio_bundle.admin.bundle_generator import BundleGeneratorDialog
from audio_bundle.admin.file_list import ReorderList, block_item
from audio_bundle.core.storage.workspace import ProjectWorkspace
from audio_bundle.shared.messages import user_message


class ProjectWindow(QWidget):

    def __init__(self, workspace: ProjectWorkspace, parent=None) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._build()
        self._refresh_blocks()
        self._update_title()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(QLabel("Project"))
        self._name = QLineEdit(self._workspace.project.name)
        self._name.setAccessibleName("Project name")
        self._name.editingFinished.connect(self._rename_project)
        header.addWidget(self._name, 1)
        save = QPushButton("Save")
        save.setShortcut(QKeySequence.StandardKey.Save)
        save.clicked.connect(self.save)
        generate = QPushButton("Generate Bundle")
        generate.clicked.connect(self._generate)
        header.addWidget(save)
        header.addWidget(generate)
        layout.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Blocks"))
        self._blocks = ReorderList()
        self._blocks.setAccessibleName("Blocks")
        self._blocks.currentRowChanged.connect(self._on_block_selected)
        self._blocks.orderChanged.connect(self._on_block_reorder)
        left_layout.addWidget(self._blocks, 1)
        block_buttons = QHBoxLayout()
        add_block = QPushButton("Add block")
        add_block.setShortcut("Ctrl+B")
        rename_block = QPushButton("Rename")
        remove_block = QPushButton("Remove block")
        add_block.clicked.connect(self._add_block)
        rename_block.clicked.connect(self._rename_block)
        remove_block.clicked.connect(self._remove_block)
        block_buttons.addWidget(add_block)
        block_buttons.addWidget(rename_block)
        block_buttons.addWidget(remove_block)
        left_layout.addLayout(block_buttons)

        self._editor = BlockEditor()
        self._editor.set_workspace(self._workspace)
        self._editor.changed.connect(self._on_editor_changed)
        splitter.addWidget(left)
        splitter.addWidget(self._editor)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        QShortcut(QKeySequence.StandardKey.Save, self, self.save)

    def _update_title(self) -> None:
        marker = " •" if self._workspace.dirty else ""
        window = self.window()
        window.setWindowTitle(f"{self._workspace.project.name}{marker} — Audio Bundle Admin")

    def _rename_project(self) -> None:
        try:
            self._workspace.set_name(self._name.text())
        except Exception as exc:
            QMessageBox.warning(self, "Audio Bundle", user_message(exc))
            self._name.setText(self._workspace.project.name)
            return
        self._update_title()

    def _refresh_blocks(self, select_id: str | None = None) -> None:
        current_id = select_id
        if current_id is None and self._blocks.currentItem() is not None:
            current_id = str(self._blocks.currentItem().data(Qt.ItemDataRole.UserRole))
        self._blocks.blockSignals(True)
        self._blocks.clear()
        for block in self._workspace.project.blocks:
            self._blocks.addItem(block_item(block))
        self._blocks.blockSignals(False)
        if not self._workspace.project.blocks:
            self._editor.show_block(None)
            return
        row = 0
        if current_id:
            for index, block in enumerate(self._workspace.project.blocks):
                if block.id == current_id:
                    row = index
                    break
        self._blocks.setCurrentRow(row)

    def _on_block_selected(self, row: int) -> None:
        if row < 0 or row >= len(self._workspace.project.blocks):
            self._editor.show_block(None)
            return
        self._editor.show_block(self._workspace.project.blocks[row].id)

    def _on_block_reorder(self) -> None:
        try:
            self._workspace.reorder_blocks(self._blocks.item_ids())
        except Exception as exc:
            QMessageBox.warning(self, "Audio Bundle", user_message(exc))
            self._refresh_blocks()
            return
        self._update_title()

    def _on_editor_changed(self) -> None:
        current = self._blocks.currentRow()
        current_id = None
        if 0 <= current < len(self._workspace.project.blocks):
            current_id = self._workspace.project.blocks[current].id
        self._refresh_blocks(current_id)
        self._update_title()

    def _add_block(self) -> None:
        name, ok = QInputDialog.getText(self, "Add block", "Block name")
        if not ok:
            return
        try:
            block = self._workspace.add_block(name)
        except Exception as exc:
            QMessageBox.warning(self, "Audio Bundle", user_message(exc))
            return
        self._refresh_blocks(block.id)
        self._update_title()

    def _rename_block(self) -> None:
        row = self._blocks.currentRow()
        if row < 0:
            return
        block = self._workspace.project.blocks[row]
        name, ok = QInputDialog.getText(self, "Rename block", "Block name", text=block.name)
        if not ok:
            return
        try:
            self._workspace.rename_block(block.id, name)
        except Exception as exc:
            QMessageBox.warning(self, "Audio Bundle", user_message(exc))
            return
        self._refresh_blocks(block.id)
        self._update_title()

    def _remove_block(self) -> None:
        row = self._blocks.currentRow()
        if row < 0:
            return
        block = self._workspace.project.blocks[row]
        confirm = QMessageBox.question(
            self,
            "Remove block",
            f"Remove “{block.name}” and its files from this project?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self._workspace.remove_block(block.id)
        except Exception as exc:
            QMessageBox.warning(self, "Audio Bundle", user_message(exc))
            return
        self._refresh_blocks()
        self._update_title()

    def save(self) -> None:
        try:
            self._workspace.set_name(self._name.text())
            self._workspace.save()
        except Exception as exc:
            QMessageBox.warning(self, "Audio Bundle", user_message(exc))
            return
        self._update_title()

    def _generate(self) -> None:
        try:
            self._workspace.set_name(self._name.text())
            self._workspace.save()
        except Exception as exc:
            QMessageBox.warning(self, "Audio Bundle", user_message(exc))
            return
        if not self._workspace.project.blocks:
            QMessageBox.information(self, "Generate Bundle", "Add at least one block before generating a bundle.")
            return
        dialog = BundleGeneratorDialog(self._workspace, self)
        dialog.exec()
        self._update_title()

    def confirm_close(self) -> bool:
        if not self._workspace.dirty:
            return True
        result = QMessageBox.question(
            self,
            "Unsaved changes",
            "Save changes before closing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if result == QMessageBox.StandardButton.Cancel:
            return False
        if result == QMessageBox.StandardButton.Save:
            self.save()
            return not self._workspace.dirty
        return True
