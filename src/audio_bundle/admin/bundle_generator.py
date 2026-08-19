from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from audio_bundle.admin.workers import GenerateBundleWorker
from audio_bundle.core.storage.workspace import ProjectWorkspace
from audio_bundle.shared.constants import BUNDLE_EXTENSION


class BundleGeneratorDialog(QDialog):
    def __init__(self, workspace: ProjectWorkspace, parent=None) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._thread: QThread | None = None
        self._worker: GenerateBundleWorker | None = None
        self._progress: QProgressDialog | None = None
        self.setWindowTitle("Generate Bundle")
        self.setModal(True)
        self.setMinimumWidth(520)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Passwords are used only to encrypt this bundle. They are not saved in the project."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        self._output = QLineEdit(str(self._workspace.default_bundle_path()))
        self._output.setAccessibleName("Bundle output path")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        output_row = QHBoxLayout()
        output_row.addWidget(self._output, 1)
        output_row.addWidget(browse)
        output_wrap = QWidget()
        output_wrap.setLayout(output_row)
        form.addRow("Output file", output_wrap)

        self._main = QLineEdit()
        self._main.setEchoMode(QLineEdit.EchoMode.Password)
        self._main.setAccessibleName("Main password")
        self._main_confirm = QLineEdit()
        self._main_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self._main_confirm.setAccessibleName("Confirm main password")
        form.addRow("Main password", self._main)
        form.addRow("Confirm main password", self._main_confirm)
        layout.addLayout(form)

        layout.addWidget(QLabel("Block passwords"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner_layout = QFormLayout(inner)
        self._block_fields: dict[str, tuple[QLineEdit, QLineEdit]] = {}
        for block in self._workspace.project.blocks:
            password = QLineEdit()
            password.setEchoMode(QLineEdit.EchoMode.Password)
            password.setAccessibleName(f"Password for {block.name}")
            confirm = QLineEdit()
            confirm.setEchoMode(QLineEdit.EchoMode.Password)
            confirm.setAccessibleName(f"Confirm password for {block.name}")
            pair = QWidget()
            pair_layout = QVBoxLayout(pair)
            pair_layout.setContentsMargins(0, 0, 0, 0)
            pair_layout.addWidget(password)
            pair_layout.addWidget(confirm)
            inner_layout.addRow(block.name, pair)
            self._block_fields[block.id] = (password, confirm)
        scroll.setWidget(inner)
        scroll.setMinimumHeight(180)
        layout.addWidget(scroll, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Generate")
        buttons.accepted.connect(self._start)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save bundle",
            self._output.text(),
            f"Audio Bundle (*{BUNDLE_EXTENSION})",
        )
        if path:
            if not path.endswith(BUNDLE_EXTENSION):
                path += BUNDLE_EXTENSION
            self._output.setText(path)

    def _start(self) -> None:
        main = self._main.text()
        if main != self._main_confirm.text():
            QMessageBox.warning(self, "Generate Bundle", "Main passwords do not match.")
            return
        if not main:
            QMessageBox.warning(self, "Generate Bundle", "Enter a main password.")
            return
        block_passwords: dict[str, str] = {}
        for block in self._workspace.project.blocks:
            password, confirm = self._block_fields[block.id]
            if password.text() != confirm.text():
                QMessageBox.warning(
                    self, "Generate Bundle", f"Passwords for “{block.name}” do not match."
                )
                return
            if not password.text():
                QMessageBox.warning(
                    self, "Generate Bundle", f"Enter a password for “{block.name}”."
                )
                return
            block_passwords[block.id] = password.text()
        output = Path(self._output.text().strip())
        if not output.name:
            QMessageBox.warning(self, "Generate Bundle", "Choose an output file.")
            return

        self._progress = QProgressDialog("Encrypting bundle…", None, 0, 0, self)
        self._progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._progress.setMinimumDuration(0)
        self._progress.setCancelButton(None)
        self._progress.show()

        self._thread = QThread(self)
        self._worker = GenerateBundleWorker(
            self._workspace, output, main, block_passwords
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.start()

    def _cleanup_progress(self) -> None:
        if self._progress is not None:
            self._progress.close()
            self._progress = None

    def _on_finished(self, path: str) -> None:
        self._cleanup_progress()
        QMessageBox.information(self, "Generate Bundle", f"Bundle saved to:\n{path}")
        self.accept()

    def _on_failed(self, message: str) -> None:
        self._cleanup_progress()
        QMessageBox.warning(self, "Generate Bundle", message)
