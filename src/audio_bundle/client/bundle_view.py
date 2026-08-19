from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressDialog,
    QVBoxLayout,
    QWidget,
)

from audio_bundle.client.workers import UnlockBlockWorker
from audio_bundle.core.bundle.session import ClientSession


class UnlockDialog(QDialog):
    def __init__(self, block_name: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(block_name)
        self.setModal(True)
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(block_name))
        layout.addWidget(QLabel("Enter block password"))
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setAccessibleName("Block password")
        layout.addWidget(self._password)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Unlock")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def password(self) -> str:
        return self._password.text()


class BundleView(QWidget):
    openBlock = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._session: ClientSession | None = None
        self._thread: QThread | None = None
        self._worker: UnlockBlockWorker | None = None
        self._pending_block: str | None = None
        self._progress: QProgressDialog | None = None
        layout = QVBoxLayout(self)
        self._title = QLabel("Course")
        self._title.setStyleSheet("font-size: 24px; font-weight: 600;")
        layout.addWidget(self._title)
        hint = QLabel("Locked blocks need a password. Unlocked blocks open the content viewer.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self._blocks = QListWidget()
        self._blocks.setAccessibleName("Blocks")
        self._blocks.itemActivated.connect(self._on_activated)
        self._blocks.itemClicked.connect(self._on_activated)
        layout.addWidget(self._blocks, 1)

    def set_session(self, session: ClientSession) -> None:
        self._session = session
        self._title.setText(session.title)
        self.refresh()

    def refresh(self) -> None:
        if self._session is None:
            return
        current = None
        if self._blocks.currentItem() is not None:
            current = str(self._blocks.currentItem().data(Qt.ItemDataRole.UserRole))
        self._blocks.clear()
        for block in self._session.opened.manifest.blocks:
            lock = "🔓" if self._session.is_unlocked(block.id) else "🔒"
            row = QListWidgetItem(f"{lock}  {block.name}")
            row.setData(Qt.ItemDataRole.UserRole, block.id)
            self._blocks.addItem(row)
            if current == block.id:
                self._blocks.setCurrentItem(row)

    def _on_activated(self, item: QListWidgetItem) -> None:
        if self._session is None or item is None:
            return
        block_id = str(item.data(Qt.ItemDataRole.UserRole))
        if self._session.is_unlocked(block_id):
            self.openBlock.emit(block_id)
            return
        name = next(b.name for b in self._session.opened.manifest.blocks if b.id == block_id)
        dialog = UnlockDialog(name, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        password = dialog.password()
        if not password:
            QMessageBox.warning(self, "Unlock", "Enter the block password.")
            return
        self._pending_block = block_id
        self._progress = QProgressDialog("Unlocking block…", None, 0, 0, self)
        self._progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._progress.setCancelButton(None)
        self._progress.setMinimumDuration(0)
        self._progress.show()
        self._thread = QThread(self)
        self._worker = UnlockBlockWorker(self._session, block_id, password)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_unlocked)
        self._worker.failed.connect(self._on_unlock_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.start()

    def _close_progress(self) -> None:
        if self._progress is not None:
            self._progress.close()
            self._progress = None

    def _on_unlocked(self, _unlocked: object) -> None:
        self._close_progress()
        block_id = self._pending_block
        self.refresh()
        if block_id:
            self.openBlock.emit(block_id)

    def _on_unlock_failed(self, message: str) -> None:
        self._close_progress()
        QMessageBox.warning(self, "Unlock", message)
