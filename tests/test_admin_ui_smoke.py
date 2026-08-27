from __future__ import annotations

import os
from pathlib import Path

import pytest


def test_admin_window_starts_offscreen() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        from audio_bundle.admin.main_window import MainWindow
    except ImportError as exc:
        pytest.skip(f"Qt libraries are not available: {exc}")

    app = QApplication.instance() or QApplication(["audio-bundle-admin"])
    window = MainWindow()
    window.show()
    app.processEvents()
    assert "Audio Bundle Admin" in window.windowTitle()
    window.close()


def test_project_window_add_folder_stays_top_level(tmp_path: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        from audio_bundle.admin.project_window import ProjectWindow
        from audio_bundle.core.storage.workspace import ProjectWorkspace
    except ImportError as extra:
        pytest.skip(f"Qt libraries are not available: {extra}")

    app = QApplication.instance() or QApplication(["audio-bundle-admin"])
    workspace = ProjectWorkspace.create(tmp_path, "Tree UI")
    day1 = workspace.add_folder()
    workspace.add_block("Block 1", parent_id=day1.id)
    window = ProjectWindow(workspace)
    window.show()
    app.processEvents()
    assert window._blocks.topLevelItemCount() == 1
    assert "Day 1" in window._blocks.topLevelItem(0).text(0)
    window._add_folder()
    app.processEvents()
    assert [folder.name for folder in workspace.project.folders] == ["Day 1", "Day 2"]
    assert all(folder.parent_id is None for folder in workspace.project.folders)
    assert window._blocks.topLevelItemCount() == 2
    window.close()
