from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from audio_bundle.client.block_view import BlockView
from audio_bundle.client.bundle_view import BundleView
from audio_bundle.client.workers import OpenBundleWorker
from audio_bundle.core.bundle.session import ClientSession
from audio_bundle.shared.constants import BUNDLE_EXTENSION


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Audio Bundle Client")
        self.resize(1000, 700)
        self._session: ClientSession | None = None
        self._thread: QThread | None = None
        self._worker: OpenBundleWorker | None = None
        self._progress: QProgressDialog | None = None
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)
        self._open_page = self._build_open_page()
        self._bundle = BundleView()
        self._block = BlockView()
        self._bundle.openBlock.connect(self._show_block)
        self._stack.addWidget(self._open_page)
        self._stack.addWidget(self._wrap_with_back(self._bundle, "Close bundle", self._close_bundle))
        self._stack.addWidget(self._wrap_with_back(self._block, "Back to blocks", self._show_bundle))

    def _wrap_with_back(self, inner: QWidget, label: str, handler) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        bar = QHBoxLayout()
        back = QPushButton(label)
        back.clicked.connect(handler)
        bar.addWidget(back)
        bar.addStretch(1)
        layout.addLayout(bar)
        layout.addWidget(inner, 1)
        return page

    def _build_open_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch(1)
        title = QLabel("Open Audio Bundle")
        title.setStyleSheet("font-size: 26px; font-weight: 600;")
        layout.addWidget(title)
        form = QFormLayout()
        path_row = QHBoxLayout()
        self._path = QLineEdit()
        self._path.setReadOnly(True)
        self._path.setAccessibleName("Bundle path")
        self._path.setPlaceholderText("No bundle selected")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        path_row.addWidget(self._path, 1)
        path_row.addWidget(browse)
        path_wrap = QWidget()
        path_wrap.setLayout(path_row)
        form.addRow("Bundle", path_wrap)
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setAccessibleName("Main password")
        self._password.returnPressed.connect(self._open_bundle)
        form.addRow("Main password", self._password)
        layout.addLayout(form)
        open_btn = QPushButton("Open")
        open_btn.setDefault(True)
        open_btn.setMinimumHeight(40)
        open_btn.setShortcut(QKeySequence.StandardKey.Open)
        open_btn.clicked.connect(self._open_bundle)
        layout.addWidget(open_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(2)
        layout.setContentsMargins(48, 48, 48, 48)
        return page

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Audio Bundle",
            self._path.text(),
            f"Audio Bundle (*{BUNDLE_EXTENSION})",
        )
        if path:
            self._path.setText(path)

    def _open_bundle(self) -> None:
        path = self._path.text().strip()
        if not path:
            QMessageBox.information(self, "Open", "Choose a .audiobundle file.")
            return
        password = self._password.text()
        if not password:
            QMessageBox.warning(self, "Open", "Enter the main password.")
            return
        self._progress = QProgressDialog("Opening bundle…", None, 0, 0, self)
        self._progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._progress.setCancelButton(None)
        self._progress.setMinimumDuration(0)
        self._progress.show()
        self._thread = QThread(self)
        self._worker = OpenBundleWorker(Path(path), password)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_opened)
        self._worker.failed.connect(self._on_open_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.start()

    def _close_progress(self) -> None:
        if self._progress is not None:
            self._progress.close()
            self._progress = None

    def _on_opened(self, session: object) -> None:
        self._close_progress()
        self._password.clear()
        self._session = session  # type: ignore[assignment]
        assert isinstance(self._session, ClientSession)
        self._bundle.set_session(self._session)
        self.setWindowTitle(f"{self._session.title} — Audio Bundle Client")
        self._stack.setCurrentIndex(1)

    def _on_open_failed(self, message: str) -> None:
        self._close_progress()
        QMessageBox.warning(self, "Open", message)

    def _show_block(self, block_id: str) -> None:
        if self._session is None:
            return
        self._block.show_block(self._session, block_id)
        self._stack.setCurrentIndex(2)

    def _show_bundle(self) -> None:
        self._block.stop()
        self._stack.setCurrentIndex(1)
        self._bundle.refresh()

    def _close_bundle(self) -> None:
        self._block.stop()
        if self._session is not None:
            self._session.close()
            self._session = None
        self.setWindowTitle("Audio Bundle Client")
        self._stack.setCurrentIndex(0)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._block.stop()
        if self._session is not None:
            self._session.close()
            self._session = None
        event.accept()
