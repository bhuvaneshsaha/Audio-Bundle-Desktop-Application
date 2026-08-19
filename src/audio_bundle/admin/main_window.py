from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from audio_bundle.admin.project_window import ProjectWindow
from audio_bundle.core.storage.workspace import ProjectWorkspace
from audio_bundle.shared.messages import user_message


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Audio Bundle Admin")
        self.resize(1100, 720)
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)
        self._welcome = self._build_welcome()
        self._project_page: ProjectWindow | None = None
        self._stack.addWidget(self._welcome)

    def _build_welcome(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch(1)
        title = QLabel("Audio Bundle Admin")
        title.setStyleSheet("font-size: 28px; font-weight: 600;")
        title.setAccessibleName("Audio Bundle Admin")
        subtitle = QLabel("Create offline encrypted course bundles. No internet required.")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        buttons = QHBoxLayout()
        new_btn = QPushButton("New project…")
        new_btn.setShortcut(QKeySequence.StandardKey.New)
        new_btn.setMinimumHeight(40)
        open_btn = QPushButton("Open project…")
        open_btn.setShortcut(QKeySequence.StandardKey.Open)
        open_btn.setMinimumHeight(40)
        new_btn.clicked.connect(self.new_project)
        open_btn.clicked.connect(self.open_project)
        buttons.addWidget(new_btn)
        buttons.addWidget(open_btn)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addStretch(2)
        for widget in (title, subtitle, new_btn, open_btn):
            widget.setMaximumWidth(640)
        layout.setContentsMargins(48, 48, 48, 48)
        return page

    def new_project(self) -> None:
        parent = QFileDialog.getExistingDirectory(self, "Choose a folder for the project")
        if not parent:
            return
        name, ok = QInputDialog.getText(self, "New project", "Course name")
        if not ok:
            return
        try:
            workspace = ProjectWorkspace.create(Path(parent), name)
        except Exception as exc:
            QMessageBox.warning(self, "Audio Bundle", user_message(exc))
            return
        self._show_project(workspace)

    def open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open project", "", "Admin project (project.json)"
        )
        if not path:
            return
        try:
            workspace = ProjectWorkspace.open(Path(path))
        except Exception as exc:
            QMessageBox.warning(self, "Audio Bundle", user_message(exc))
            return
        self._show_project(workspace)

    def _show_project(self, workspace: ProjectWorkspace) -> None:
        if self._project_page is not None:
            self._stack.removeWidget(self._project_page)
            self._project_page.deleteLater()
        self._project_page = ProjectWindow(workspace)
        self._stack.addWidget(self._project_page)
        self._stack.setCurrentWidget(self._project_page)
        self._project_page._update_title()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._project_page is not None and not self._project_page.confirm_close():
            event.ignore()
            return
        event.accept()
