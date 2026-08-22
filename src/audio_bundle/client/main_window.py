from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
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
from audio_bundle.client.shortcuts import HELP_TEXT
from audio_bundle.client.windows_login import WindowsSignInForm
from audio_bundle.client.workers import OpenBundleWorker
from audio_bundle.core.auth.windows import default_authenticator
from audio_bundle.core.bundle.session import ClientSession
from audio_bundle.shared.constants import BUNDLE_EXTENSION
from audio_bundle.shared.messages import user_message
from audio_bundle.shared.qt_paths import last_dir, remember_path


class MainWindow(QMainWindow):
    def __init__(self, *, authenticator=None) -> None:
        super().__init__()
        self.setWindowTitle("Audio Bundle Client")
        self.resize(1000, 700)
        self._authenticator = authenticator or default_authenticator()
        self._windows_identity = None
        self._session: ClientSession | None = None
        self._thread: QThread | None = None
        self._worker: OpenBundleWorker | None = None
        self._progress: QProgressDialog | None = None
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)
        self._sign_in_page = self._build_sign_in_page()
        self._open_page = self._build_open_page()
        self._bundle = BundleView()
        self._block = BlockView()
        self._bundle.openBlock.connect(self._show_block)
        self._stack.addWidget(self._sign_in_page)
        self._stack.addWidget(self._open_page)
        self._bundle_page = self._wrap_with_back(self._bundle, "Close bundle (Esc)", self._close_bundle)
        self._block_page = self._wrap_with_back(self._block, "Back to blocks (Esc)", self._show_bundle)
        self._stack.addWidget(self._bundle_page)
        self._stack.addWidget(self._block_page)
        QShortcut(QKeySequence.StandardKey.HelpContents, self, self._show_shortcuts)
        QShortcut(QKeySequence("F1"), self, self._show_shortcuts)
        QShortcut(QKeySequence("Esc"), self, self._go_back)
        self._sign_in_form.username.setFocus()

    def _wrap_with_back(self, inner: QWidget, label: str, handler) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        bar = QHBoxLayout()
        back = QPushButton(label)
        back.clicked.connect(handler)
        help_btn = QPushButton("Keyboard shortcuts (F1)")
        help_btn.clicked.connect(self._show_shortcuts)
        bar.addWidget(back)
        bar.addStretch(1)
        bar.addWidget(help_btn)
        layout.addLayout(bar)
        layout.addWidget(inner, 1)
        return page

    def _build_sign_in_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch(1)
        title = QLabel("Sign in to Audio Bundle Client")
        title.setStyleSheet("font-size: 26px; font-weight: 600;")
        layout.addWidget(title)
        intro = QLabel(
            "Sign in with a Windows user name and password even if this PC is already logged on. "
            "Shared machines can have more than one user. "
            "When this PC joins Active Directory, use DOMAIN\\user or user@domain."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self._sign_in_form = WindowsSignInForm(title="")
        self._sign_in_form.hello.clicked.connect(self._sign_in_hello)
        self._sign_in_form.password.returnPressed.connect(self._complete_windows_sign_in)
        layout.addWidget(self._sign_in_form)
        sign_in = QPushButton("Sign in")
        sign_in.setDefault(True)
        sign_in.setMinimumHeight(40)
        sign_in.setShortcut(QKeySequence("Return"))
        sign_in.clicked.connect(self._complete_windows_sign_in)
        layout.addWidget(sign_in, alignment=Qt.AlignmentFlag.AlignLeft)
        help_btn = QPushButton("Keyboard shortcuts (F1)")
        help_btn.clicked.connect(self._show_shortcuts)
        layout.addWidget(help_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(2)
        layout.setContentsMargins(48, 48, 48, 48)
        return page

    def _build_open_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch(1)
        title = QLabel("Open Audio Bundle")
        title.setStyleSheet("font-size: 26px; font-weight: 600;")
        layout.addWidget(title)
        self._signed_in_label = QLabel("")
        self._signed_in_label.setWordWrap(True)
        layout.addWidget(self._signed_in_label)
        form = QFormLayout()
        path_row = QHBoxLayout()
        self._path = QLineEdit()
        self._path.setReadOnly(True)
        self._path.setAccessibleName("Bundle path")
        self._path.setPlaceholderText("No bundle selected")
        browse = QPushButton("Browse…")
        browse.setShortcut("Alt+B")
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
        sign_out = QPushButton("Sign out Windows account")
        sign_out.clicked.connect(self._sign_out)
        layout.addWidget(sign_out, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(2)
        layout.setContentsMargins(48, 48, 48, 48)
        return page

    def _show_shortcuts(self) -> None:
        QMessageBox.information(self, "Keyboard shortcuts", HELP_TEXT)

    def _go_back(self) -> None:
        index = self._stack.currentIndex()
        if index == 3:
            self._show_bundle()
        elif index == 2:
            self._close_bundle()

    def _sign_in_hello(self) -> None:
        try:
            identity = self._authenticator.verify_hello()
        except Exception as exc:
            QMessageBox.information(self, "Windows Hello", user_message(exc))
            return
        self._accept_identity(identity)

    def _complete_windows_sign_in(self) -> None:
        username, password = self._sign_in_form.credentials()
        try:
            identity = self._authenticator.verify_password(username, password)
        except Exception as exc:
            QMessageBox.warning(self, "Windows sign-in", user_message(exc))
            return
        self._accept_identity(identity)

    def _accept_identity(self, identity) -> None:
        self._windows_identity = identity
        self._signed_in_label.setText(f"Signed in as {identity.display_name()}")
        self._sign_in_form.password.clear()
        self._stack.setCurrentIndex(1)
        self._password.setFocus()

    def _sign_out(self) -> None:
        self._close_bundle()
        self._windows_identity = None
        self._stack.setCurrentIndex(0)
        self._sign_in_form.username.setFocus()

    def _browse(self) -> None:
        start = self._path.text() or last_dir("Client", "last_bundle_dir")
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Audio Bundle",
            start,
            f"Audio Bundle (*{BUNDLE_EXTENSION})",
        )
        if path:
            self._path.setText(path)
            remember_path("Client", "last_bundle_dir", path)

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
        self._bundle.set_session(self._session, authenticator=self._authenticator)
        self.setWindowTitle(f"{self._session.title} — Audio Bundle Client")
        self._stack.setCurrentIndex(2)

    def _on_open_failed(self, message: str) -> None:
        self._close_progress()
        QMessageBox.warning(self, "Open", message)

    def _show_block(self, block_id: str) -> None:
        if self._session is None:
            return
        self._block.show_block(self._session, block_id)
        self._stack.setCurrentIndex(3)

    def _show_bundle(self) -> None:
        self._block.stop()
        self._stack.setCurrentIndex(2)
        self._bundle.refresh()
        self._bundle._blocks.setFocus()

    def _close_bundle(self) -> None:
        self._block.stop()
        if self._session is not None:
            self._session.close()
            self._session = None
        self.setWindowTitle("Audio Bundle Client")
        self._stack.setCurrentIndex(1)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._block.stop()
        if self._session is not None:
            self._session.close()
            self._session = None
        event.accept()
