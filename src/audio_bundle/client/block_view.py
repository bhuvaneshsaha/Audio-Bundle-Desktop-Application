from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressDialog,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from audio_bundle.client.audio_player import AudioPlayer
from audio_bundle.client.pdf_viewer import PdfViewer
from audio_bundle.client.workers import DecryptFileWorker
from audio_bundle.core.bundle.session import ClientSession
from audio_bundle.core.models.manifest import BundleFileEntry
from audio_bundle.core.models.media_type import MediaType


class BlockView(QWidget):
    requestBack = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._session: ClientSession | None = None
        self._block_id: str | None = None
        self._thread: QThread | None = None
        self._worker: DecryptFileWorker | None = None
        self._progress: QProgressDialog | None = None
        layout = QVBoxLayout(self)
        self._title = QLabel("Block")
        self._title.setStyleSheet("font-size: 22px; font-weight: 600;")
        layout.addWidget(self._title)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._files = QListWidget()
        self._files.setAccessibleName("Block contents")
        self._files.currentRowChanged.connect(self._on_file_selected)
        splitter.addWidget(self._files)
        self._stack = QStackedWidget()
        self._empty = QLabel("Select a file to decrypt and view it in the application.")
        self._empty.setWordWrap(True)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._audio = AudioPlayer()
        self._pdf = PdfViewer()
        self._stack.addWidget(self._empty)
        self._stack.addWidget(self._audio)
        self._stack.addWidget(self._pdf)
        self._audio.requestFile.connect(self._select_file)
        splitter.addWidget(self._stack)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

    def show_block(self, session: ClientSession, block_id: str) -> None:
        self.stop()
        self._session = session
        self._block_id = block_id
        contents = session.block_contents(block_id)
        self._title.setText(contents.name)
        self._audio.set_files(contents.files)
        self._files.clear()
        for entry in contents.files:
            kind = "PDF" if entry.media_type is MediaType.PDF else "Audio"
            row = QListWidgetItem(f"{entry.display_name}    ({kind})")
            row.setData(Qt.ItemDataRole.UserRole, entry.id)
            row.setToolTip(entry.original_filename)
            self._files.addItem(row)
        self._stack.setCurrentWidget(self._empty)
        if self._files.count():
            self._files.setCurrentRow(0)

    def stop(self) -> None:
        self._audio.stop()
        self._pdf.clear()

    def _on_file_selected(self, row: int) -> None:
        if self._session is None or self._block_id is None or row < 0:
            return
        item = self._files.item(row)
        if item is None:
            return
        file_id = str(item.data(Qt.ItemDataRole.UserRole))
        self._audio.stop()
        self._progress = QProgressDialog("Decrypting…", None, 0, 0, self)
        self._progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._progress.setMinimumDuration(0)
        self._progress.setCancelButton(None)
        self._progress.show()
        self._thread = QThread(self)
        self._worker = DecryptFileWorker(self._session, self._block_id, file_id)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_decrypted)
        self._worker.failed.connect(self._on_decrypt_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.start()

    def _close_progress(self) -> None:
        if self._progress is not None:
            self._progress.close()
            self._progress = None

    def _on_decrypted(self, entry: BundleFileEntry, path: Path) -> None:
        self._close_progress()
        if entry.media_type is MediaType.PDF:
            self._pdf.load(entry, path)
            self._stack.setCurrentWidget(self._pdf)
        else:
            self._audio.load(entry, path)
            self._stack.setCurrentWidget(self._audio)

    def _select_file(self, file_id: str) -> None:
        for row in range(self._files.count()):
            item = self._files.item(row)
            if item is not None and str(item.data(Qt.ItemDataRole.UserRole)) == file_id:
                if self._files.currentRow() == row:
                    self._on_file_selected(row)
                else:
                    self._files.setCurrentRow(row)
                return

    def _on_decrypt_failed(self, message: str) -> None:
        self._close_progress()
        self._stack.setCurrentWidget(self._empty)
        QMessageBox.warning(self, "Audio Bundle", message)
