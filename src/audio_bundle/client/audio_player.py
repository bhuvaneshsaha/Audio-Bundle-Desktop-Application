from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from audio_bundle.core.models.manifest import BundleFileEntry


class AudioPlayer(QWidget):
    """Basic playback for the content viewer. Full transport controls are Milestone 6."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._player.setAudioOutput(self._audio)
        layout = QVBoxLayout(self)
        self._now = QLabel("No audio selected")
        self._now.setStyleSheet("font-size: 16px; font-weight: 600;")
        self._now.setWordWrap(True)
        layout.addWidget(QLabel("Now Playing"))
        layout.addWidget(self._now)
        buttons = QHBoxLayout()
        self._play = QPushButton("Play")
        self._pause = QPushButton("Pause")
        self._stop = QPushButton("Stop")
        self._play.clicked.connect(self._player.play)
        self._pause.clicked.connect(self._player.pause)
        self._stop.clicked.connect(self._player.stop)
        buttons.addWidget(self._play)
        buttons.addWidget(self._pause)
        buttons.addWidget(self._stop)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        note = QLabel("Seek, speed, and playlist controls arrive in the full audio player.")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)

    def load(self, entry: BundleFileEntry, path: Path) -> None:
        self._now.setText(entry.display_name)
        self._player.setSource(QUrl.fromLocalFile(str(path)))
        self._player.play()

    def stop(self) -> None:
        self._player.stop()
