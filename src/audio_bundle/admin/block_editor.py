from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from audio_bundle.admin.constants import FILE_FILTER
from audio_bundle.admin.file_list import ReorderList, file_item
from audio_bundle.admin.password_field import PasswordField
from audio_bundle.admin.workers import ImportFilesWorker
from audio_bundle.core.models.auth_method import BlockAuthMethod
from audio_bundle.core.storage.workspace import ProjectWorkspace
from audio_bundle.shared.messages import user_message
from audio_bundle.shared.qt_paths import last_dir, remember_path


class BlockEditor(QWidget):
    changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._workspace: ProjectWorkspace | None = None
        self._block_id: str | None = None
        self._thread: QThread | None = None
        self._worker: ImportFilesWorker | None = None

        layout = QVBoxLayout(self)
        self._title = QLabel("Select a block")
        self._title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(self._title)

        layout.addWidget(QLabel("Unlock method"))
        self._auth = QComboBox()
        self._auth.setAccessibleName("Block authentication method")
        self._auth.addItem("Custom password", "password")
        self._auth.addItem("Windows authentication", "windows")
        self._auth.addItem("No password", "none")
        self._auth.currentIndexChanged.connect(self._on_auth_changed)
        layout.addWidget(self._auth)

        self._password = PasswordField("Block password")
        self._password.editingFinished().connect(self._store_password)
        self._password.textEdited().connect(lambda _text: self._store_password())
        self._password_hint = QLabel(
            "This password is kept for this session only. It is not saved in the project file."
        )
        self._password_hint.setWordWrap(True)
        layout.addWidget(self._password)
        layout.addWidget(self._password_hint)

        self._windows_hint = QLabel(
            "The Client will ask for a Windows user name and password. "
            "Optional allow-list (one account per line), for example DOMAIN\\user or user@contoso.com. "
            "Leave empty to allow any Windows account that signs in successfully. "
            "After machines join Active Directory, the same names and group:DOMAIN\\Group entries apply."
        )
        self._windows_hint.setWordWrap(True)
        self._windows = QPlainTextEdit()
        self._windows.setAccessibleName("Allowed Windows users")
        self._windows.setPlaceholderText("DOMAIN\\user  or  user@domain")
        self._windows.setMaximumHeight(90)
        self._windows.textChanged.connect(self._store_auth)
        layout.addWidget(self._windows_hint)
        layout.addWidget(self._windows)

        self._none_hint = QLabel(
            "This block unlocks without a block password after the Client main password and Windows sign-in."
        )
        self._none_hint.setWordWrap(True)
        layout.addWidget(self._none_hint)

        self._files = ReorderList()
        self._files.setAccessibleName("Block files")
        self._files.orderChanged.connect(self._on_reorder)
        layout.addWidget(self._files, 1)

        buttons = QHBoxLayout()
        self._add = QPushButton("Add files…")
        self._add.setShortcut("Ctrl+I")
        self._rename = QPushButton("Rename")
        self._remove = QPushButton("Remove file")
        self._remove.setShortcut("Delete")
        self._add.clicked.connect(self._import_files)
        self._rename.clicked.connect(self._rename_file)
        self._remove.clicked.connect(self._remove_file)
        buttons.addWidget(self._add)
        buttons.addWidget(self._rename)
        buttons.addWidget(self._remove)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self._set_enabled(False)

    def set_workspace(self, workspace: ProjectWorkspace) -> None:
        self._workspace = workspace
        self.show_block(None)

    def show_block(self, block_id: str | None) -> None:
        self._store_password()
        self._block_id = block_id
        if self._workspace is None or block_id is None:
            self._title.setText("Select a block")
            self._files.clear()
            self._password.setText("")
            self._windows.setPlainText("")
            self._set_enabled(False)
            return
        block = self._workspace.project.get_block(block_id)
        self._title.setText(block.name)
        self._auth.blockSignals(True)
        index = self._auth.findData(str(block.auth_method))
        self._auth.setCurrentIndex(index if index >= 0 else 0)
        self._auth.blockSignals(False)
        self._windows.blockSignals(True)
        self._windows.setPlainText("\n".join(block.windows_principals))
        self._windows.blockSignals(False)
        self._password.setText(self._workspace.block_password(block_id))
        self._files.clear()
        for item in block.items:
            self._files.addItem(file_item(item))
        self._set_enabled(True)
        self._sync_auth_widgets()

    def _set_enabled(self, enabled: bool) -> None:
        for widget in (self._files, self._add, self._rename, self._remove, self._password, self._auth, self._windows):
            widget.setEnabled(enabled)
        if enabled:
            self._sync_auth_widgets()

    def _auth_method(self) -> BlockAuthMethod:
        from audio_bundle.core.models.auth_method import parse_block_auth_method

        return parse_block_auth_method(self._auth.currentData())

    def _sync_auth_widgets(self) -> None:
        method = self._auth_method()
        password = method is BlockAuthMethod.PASSWORD
        windows = method is BlockAuthMethod.WINDOWS
        self._password.setVisible(password)
        self._password_hint.setVisible(password)
        self._windows.setVisible(windows)
        self._windows_hint.setVisible(windows)
        self._none_hint.setVisible(method is BlockAuthMethod.NONE)

    def _on_auth_changed(self) -> None:
        self._sync_auth_widgets()
        self._store_auth()
        self.changed.emit()

    def _store_auth(self) -> None:
        if self._workspace is None or self._block_id is None:
            return
        principals = [line.strip() for line in self._windows.toPlainText().splitlines() if line.strip()]
        self._workspace.set_block_auth(self._block_id, self._auth_method(), windows_principals=principals)

    def flush_password(self) -> None:
        self._store_password()
        self._store_auth()

    def _store_password(self) -> None:
        if self._workspace is None or self._block_id is None:
            return
        self._workspace.set_block_password(self._block_id, self._password.text())

    def _on_reorder(self) -> None:
        if self._workspace is None or self._block_id is None:
            return
        try:
            self._workspace.reorder_items(self._block_id, self._files.item_ids())
        except Exception as exc:
            QMessageBox.warning(self, "Audio Bundle", user_message(exc))
            self.show_block(self._block_id)
            return
        self.changed.emit()

    def _import_files(self) -> None:
        if self._workspace is None or self._block_id is None:
            return
        self._store_password()
        start = last_dir("Admin", "last_import_dir", str(Path.home()))
        paths, _ = QFileDialog.getOpenFileNames(self, "Import files", start, FILE_FILTER)
        if not paths:
            return
        remember_path("Admin", "last_import_dir", paths[0])
        self._add.setEnabled(False)
        self._thread = QThread(self)
        self._worker = ImportFilesWorker(self._workspace, self._block_id, [Path(p) for p in paths])
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_imported)
        self._worker.failed.connect(self._on_import_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.start()

    def _on_imported(self, count: int) -> None:
        self._add.setEnabled(True)
        self.show_block(self._block_id)
        self.changed.emit()
        QMessageBox.information(self, "Import", f"Imported {count} file{'s' if count != 1 else ''}.")

    def _on_import_failed(self, message: str) -> None:
        self._add.setEnabled(True)
        self.show_block(self._block_id)
        QMessageBox.warning(self, "Import", message)

    def _rename_file(self) -> None:
        if self._workspace is None or self._block_id is None:
            return
        row = self._files.currentItem()
        if row is None:
            return
        item_id = str(row.data(Qt.ItemDataRole.UserRole))
        current = self._workspace.project.get_block(self._block_id)
        match = next((item for item in current.items if item.id == item_id), None)
        if match is None:
            return
        name, ok = QInputDialog.getText(self, "Rename file", "Display name", text=match.display_name)
        if not ok:
            return
        try:
            self._workspace.rename_item(self._block_id, item_id, name)
        except Exception as exc:
            QMessageBox.warning(self, "Audio Bundle", user_message(exc))
            return
        self.show_block(self._block_id)
        self.changed.emit()

    def _remove_file(self) -> None:
        if self._workspace is None or self._block_id is None:
            return
        row = self._files.currentItem()
        if row is None:
            return
        item_id = str(row.data(Qt.ItemDataRole.UserRole))
        confirm = QMessageBox.question(
            self,
            "Remove file",
            "Remove this file from the block? The copied source file will be deleted from the project folder.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self._workspace.remove_item(self._block_id, item_id)
        except Exception as exc:
            QMessageBox.warning(self, "Audio Bundle", user_message(exc))
            return
        self.show_block(self._block_id)
        self.changed.emit()
