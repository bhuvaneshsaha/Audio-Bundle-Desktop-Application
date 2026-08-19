from __future__ import annotations

import os

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
