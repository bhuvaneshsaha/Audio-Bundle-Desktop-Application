from __future__ import annotations

import os

import pytest


def test_client_window_starts_offscreen() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        from audio_bundle.client.main_window import MainWindow
    except ImportError as exc:
        pytest.skip(f"Qt libraries are not available: {exc}")

    app = QApplication.instance() or QApplication(["audio-bundle-client"])
    window = MainWindow()
    window.show()
    app.processEvents()
    assert "Audio Bundle Client" in window.windowTitle()
    window.close()
