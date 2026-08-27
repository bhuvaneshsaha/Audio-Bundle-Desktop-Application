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


def test_block_status_icon_uses_lock_unlock_not_arrow() -> None:
    from audio_bundle.client.block_status import block_status_icon

    assert block_status_icon(unlocked=False, opened=False, sequence_locked=False) == "🔒"
    assert block_status_icon(unlocked=True, opened=True, sequence_locked=False) == "🔓"
    assert block_status_icon(unlocked=False, opened=False, sequence_locked=True) == "🔒"
    assert block_status_icon(unlocked=False, opened=True, sequence_locked=False) == "✓"
    for args in (
        {"unlocked": False, "opened": False, "sequence_locked": False},
        {"unlocked": True, "opened": True, "sequence_locked": False},
        {"unlocked": False, "opened": False, "sequence_locked": True},
    ):
        mark = block_status_icon(**args)
        assert "▸" not in mark
        assert "→" not in mark
