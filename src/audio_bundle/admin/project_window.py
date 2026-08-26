from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from audio_bundle.admin.block_editor import BlockEditor
from audio_bundle.admin.bundle_generator import BundleGeneratorDialog
from audio_bundle.admin.course_tree import CourseTree
from audio_bundle.core.models.auth_method import BlockAuthMethod
from audio_bundle.core.models.node import NodeType
from audio_bundle.core.storage.workspace import ProjectWorkspace
from audio_bundle.shared.constants import MAX_FOLDER_DEPTH
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
        self._autoplay = QCheckBox("Auto-play the first audio file when a client opens a block")
        self._autoplay.setChecked(self._workspace.project.autoplay_on_open)
        self._autoplay.toggled.connect(self._set_autoplay)
        layout.addWidget(self._autoplay)
        self._single = QCheckBox("Allow only one unlocked block at a time (opening another block locks the previous one)")
        self._single.setChecked(self._workspace.project.single_active_block)
        self._single.toggled.connect(self._set_single)
        layout.addWidget(self._single)
        self._sequential = QCheckBox(
            "Blocks in the same folder must be opened in order. Other folders are independent."
        )
        self._sequential.setChecked(self._workspace.project.sequential_unlock)
        self._sequential.toggled.connect(self._set_sequential)
        layout.addWidget(self._sequential)

        auth_row = QHBoxLayout()
        auth_row.addWidget(QLabel("Block unlock method (all blocks)"))
        self._auth = QComboBox()
        self._auth.setAccessibleName("Block unlock method")
        self._auth.addItem("Custom password", "password")
        self._auth.addItem("Windows authentication", "windows")
        self._auth.addItem("No password", "none")
        index = self._auth.findData(str(self._workspace.project.block_auth_method))
        self._auth.setCurrentIndex(index if index >= 0 else 0)
        self._auth.currentIndexChanged.connect(self._set_auth_method)
        auth_row.addWidget(self._auth, 1)
        layout.addLayout(auth_row)
        self._windows_hint = QLabel(
            "Client users sign in with Windows (password, PIN, or fingerprint for the current account). "
            "Optional allow-list, one account per line: DOMAIN\\user or user@domain. "
            "Empty list = any Windows account that signs in. After Active Directory join, the same names apply."
        )
        self._windows_hint.setWordWrap(True)
        self._windows = QPlainTextEdit()
        self._windows.setAccessibleName("Allowed Windows users")
        self._windows.setPlaceholderText(r"DOMAIN\user  or  user@domain")
        self._windows.setMaximumHeight(80)
        self._windows.setPlainText("\n".join(self._workspace.project.windows_principals))
        self._windows.textChanged.connect(self._store_windows_principals)
        layout.addWidget(self._windows_hint)
        layout.addWidget(self._windows)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Folders and blocks"))
        self._blocks = CourseTree()
        self._blocks.selectionChangedId.connect(self._on_tree_selected)
        left_layout.addWidget(self._blocks, 1)
        block_buttons = QHBoxLayout()
        add_folder = QPushButton("Add folder")
        add_block = QPushButton("Add block")
        add_block.setShortcut("Ctrl+B")
        rename_block = QPushButton("Rename")
        remove_block = QPushButton("Remove")
        move_up = QPushButton("Move up")
        move_down = QPushButton("Move down")
        add_folder.clicked.connect(self._add_folder)
        add_block.clicked.connect(self._add_block)
        rename_block.clicked.connect(self._rename_node)
        remove_block.clicked.connect(self._remove_node)
        move_up.clicked.connect(lambda: self._move_node(-1))
        move_down.clicked.connect(lambda: self._move_node(1))
        block_buttons.addWidget(add_folder)
        block_buttons.addWidget(add_block)
        block_buttons.addWidget(rename_block)
        block_buttons.addWidget(remove_block)
        left_layout.addLayout(block_buttons)
        order_buttons = QHBoxLayout()
        order_buttons.addWidget(move_up)
        order_buttons.addWidget(move_down)
        left_layout.addLayout(order_buttons)

        self._editor = BlockEditor()
        self._editor.set_workspace(self._workspace)
        self._editor.changed.connect(self._on_editor_changed)
        splitter.addWidget(left)
        splitter.addWidget(self._editor)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        QShortcut(QKeySequence.StandardKey.Save, self, self.save)
        self._sync_auth_widgets()

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
        current_id = select_id or self._blocks.selected_id()
        self._blocks.rebuild(self._workspace.project, current_id)
        self._on_tree_selected()

    def _set_autoplay(self, enabled: bool) -> None:
        self._workspace.set_autoplay_on_open(enabled)
        self._update_title()

    def _set_single(self, enabled: bool) -> None:
        self._workspace.set_single_active_block(enabled)
        self._update_title()

    def _set_sequential(self, enabled: bool) -> None:
        self._workspace.set_sequential_unlock(enabled)
        self._update_title()

    def _sync_auth_widgets(self) -> None:
        windows = self._workspace.project.block_auth_method is BlockAuthMethod.WINDOWS
        self._windows.setVisible(windows)
        self._windows_hint.setVisible(windows)
        self._editor.sync_auth_ui()

    def _set_auth_method(self) -> None:
        method = self._auth.currentData()
        principals = [line.strip() for line in self._windows.toPlainText().splitlines() if line.strip()]
        self._workspace.set_block_auth_method(method, windows_principals=principals)
        self._sync_auth_widgets()
        self._update_title()

    def _store_windows_principals(self) -> None:
        if self._workspace.project.block_auth_method is not BlockAuthMethod.WINDOWS:
            return
        principals = [line.strip() for line in self._windows.toPlainText().splitlines() if line.strip()]
        self._workspace.set_block_auth_method(BlockAuthMethod.WINDOWS, windows_principals=principals)
        self._update_title()

    def _on_tree_selected(self) -> None:
        if self._blocks.selected_kind() == str(NodeType.BLOCK):
            self._editor.show_block(self._blocks.selected_id())
        else:
            self._editor.show_block(None)

    def _folder_parent_for_new(self) -> str | None:
        kind = self._blocks.selected_kind()
        node_id = self._blocks.selected_id()
        if kind is None or node_id is None:
            return None
        if kind == str(NodeType.FOLDER):
            depth = self._workspace.project.folder_depth_of(node_id)
            if depth >= MAX_FOLDER_DEPTH:
                return self._workspace.project.get_folder(node_id).parent_id
            return node_id
        return self._workspace.project.get_block(node_id).parent_id

    def _block_parent_for_new(self) -> str | None:
        kind = self._blocks.selected_kind()
        node_id = self._blocks.selected_id()
        if kind == str(NodeType.FOLDER) and node_id:
            return node_id
        if kind == str(NodeType.BLOCK) and node_id:
            return self._workspace.project.get_block(node_id).parent_id
        return None

    def _on_editor_changed(self) -> None:
        self._refresh_blocks(self._blocks.selected_id())
        self._update_title()

    def _add_folder(self) -> None:
        parent_id = self._folder_parent_for_new()
        name = None
        if parent_id is not None:
            suggested = self._workspace.project.default_nested_folder_name(parent_id)
            name, ok = QInputDialog.getText(self, "Add folder", "Folder name", text=suggested)
            if not ok:
                return
        try:
            folder = self._workspace.add_folder(name, parent_id=parent_id)
        except Exception as exc:
            QMessageBox.warning(self, "Audio Bundle", user_message(exc))
            return
        self._refresh_blocks(folder.id)
        self._update_title()

    def _add_block(self) -> None:
        try:
            block = self._workspace.add_block(parent_id=self._block_parent_for_new())
        except Exception as exc:
            QMessageBox.warning(self, "Audio Bundle", user_message(exc))
            return
        self._refresh_blocks(block.id)
        self._update_title()

    def _rename_node(self) -> None:
        node_id = self._blocks.selected_id()
        kind = self._blocks.selected_kind()
        if node_id is None or kind is None:
            return
        if kind == str(NodeType.FOLDER):
            current = self._workspace.project.get_folder(node_id).name
            title, label = "Rename folder", "Folder name"
        else:
            current = self._workspace.project.get_block(node_id).name
            title, label = "Rename block", "Block name"
        name, ok = QInputDialog.getText(self, title, label, text=current)
        if not ok:
            return
        try:
            if kind == str(NodeType.FOLDER):
                self._workspace.rename_folder(node_id, name)
            else:
                self._workspace.rename_block(node_id, name)
        except Exception as exc:
            QMessageBox.warning(self, "Audio Bundle", user_message(exc))
            return
        self._refresh_blocks(node_id)
        self._update_title()

    def _remove_node(self) -> None:
        node_id = self._blocks.selected_id()
        kind = self._blocks.selected_kind()
        if node_id is None or kind is None:
            return
        if kind == str(NodeType.FOLDER):
            folder = self._workspace.project.get_folder(node_id)
            confirm = QMessageBox.question(
                self,
                "Remove folder",
                f"Remove “{folder.name}” and everything inside it? Folders are organizational only; "
                "blocks inside will be deleted from this project.",
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
            try:
                self._workspace.remove_folder(node_id)
            except Exception as exc:
                QMessageBox.warning(self, "Audio Bundle", user_message(exc))
                return
        else:
            block = self._workspace.project.get_block(node_id)
            confirm = QMessageBox.question(
                self,
                "Remove block",
                f"Remove “{block.name}” and its files from this project?",
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
            try:
                self._workspace.remove_block(node_id)
            except Exception as exc:
                QMessageBox.warning(self, "Audio Bundle", user_message(exc))
                return
        self._refresh_blocks()
        self._update_title()

    def _move_node(self, delta: int) -> None:
        node_id = self._blocks.selected_id()
        if node_id is None:
            return
        try:
            self._workspace.move_node(node_id, delta=delta)
        except Exception as exc:
            QMessageBox.warning(self, "Audio Bundle", user_message(exc))
            self._refresh_blocks(node_id)
            return
        self._refresh_blocks(node_id)
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
        self._editor.flush_password()
        try:
            self._workspace.set_name(self._name.text())
            self._workspace.save()
        except Exception as exc:
            QMessageBox.warning(self, "Audio Bundle", user_message(exc))
            return
        if not self._workspace.project.blocks:
            QMessageBox.information(self, "Generate Bundle", "Add at least one block before generating a bundle.")
            return
        missing = self._workspace.missing_password_block_names()
        if missing:
            QMessageBox.warning(
                self,
                "Generate Bundle",
                "Set a password on every block before generating:\n- " + "\n- ".join(missing),
            )
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
