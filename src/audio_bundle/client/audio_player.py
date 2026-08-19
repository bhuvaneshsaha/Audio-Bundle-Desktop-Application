from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from audio_bundle.core.models.manifest import BundleFileEntry
from audio_bundle.core.playback import (
    PLAYBACK_SPEEDS,
    SEEK_STEP_MS,
    format_position,
    next_audio,
    previous_audio,
)


class AudioPlayer(QWidget):
    requestFile = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._files: list[BundleFileEntry] = []
        self._current: BundleFileEntry | None = None
        self._seeking = False
        self._unmuted_volume = 0.8
        self._suppress_finished = False
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._audio.setVolume(self._unmuted_volume)
        self._player.setAudioOutput(self._audio)
        self._player.positionChanged.connect(self._on_position)
        self._player.durationChanged.connect(self._on_duration)
        self._player.playbackStateChanged.connect(self._on_state)
        self._player.mediaStatusChanged.connect(self._on_status)
        self._player.errorOccurred.connect(self._on_error)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Now Playing"))
        self._now = QLabel("No audio selected")
        self._now.setStyleSheet("font-size: 16px; font-weight: 600;")
        self._now.setWordWrap(True)
        self._now.setAccessibleName("Now playing")
        layout.addWidget(self._now)

        seek_row = QHBoxLayout()
        self._elapsed = QLabel("00:00")
        self._remaining = QLabel("00:00")
        self._seek = QSlider(Qt.Orientation.Horizontal)
        self._seek.setAccessibleName("Seek")
        self._seek.sliderPressed.connect(lambda: setattr(self, "_seeking", True))
        self._seek.sliderReleased.connect(self._seek_released)
        seek_row.addWidget(self._elapsed)
        seek_row.addWidget(self._seek, 1)
        seek_row.addWidget(self._remaining)
        layout.addLayout(seek_row)

        transport = QHBoxLayout()
        self._back = QPushButton("-10")
        self._prev = QPushButton("Previous")
        self._play = QPushButton("Play")
        self._next = QPushButton("Next")
        self._forward = QPushButton("+10")
        self._stop = QPushButton("Stop")
        self._back.clicked.connect(lambda: self._nudge(-SEEK_STEP_MS))
        self._forward.clicked.connect(lambda: self._nudge(SEEK_STEP_MS))
        self._prev.clicked.connect(self._play_previous)
        self._next.clicked.connect(self._play_next)
        self._play.clicked.connect(self._toggle_play)
        self._stop.clicked.connect(self.stop)
        for button in (self._back, self._prev, self._play, self._next, self._forward, self._stop):
            button.setMinimumHeight(36)
            transport.addWidget(button)
        layout.addLayout(transport)

        extras = QHBoxLayout()
        extras.addWidget(QLabel("Speed"))
        self._speed = QComboBox()
        self._speed.setAccessibleName("Playback speed")
        for rate in PLAYBACK_SPEEDS:
            self._speed.addItem(f"{rate:g}x", rate)
        self._speed.setCurrentIndex(PLAYBACK_SPEEDS.index(1.0))
        self._speed.currentIndexChanged.connect(self._apply_speed)
        extras.addWidget(self._speed)
        extras.addWidget(QLabel("Volume"))
        self._volume = QSlider(Qt.Orientation.Horizontal)
        self._volume.setRange(0, 100)
        self._volume.setValue(80)
        self._volume.setAccessibleName("Volume")
        self._volume.valueChanged.connect(self._apply_volume)
        extras.addWidget(self._volume, 1)
        self._mute = QPushButton("Mute")
        self._mute.setCheckable(True)
        self._mute.toggled.connect(self._apply_mute)
        extras.addWidget(self._mute)
        layout.addLayout(extras)
        self._error = QLabel("")
        self._error.setWordWrap(True)
        layout.addWidget(self._error)
        layout.addStretch(1)

    def set_files(self, files: list[BundleFileEntry]) -> None:
        self._files = list(files)

    def load(self, entry: BundleFileEntry, path: Path) -> None:
        self._suppress_finished = True
        self._current = entry
        self._now.setText(entry.display_name)
        self._error.setText("")
        self._player.setSource(QUrl.fromLocalFile(str(path)))
        self._apply_speed()
        self._player.play()

    def stop(self) -> None:
        """Stop playback without advancing to the next track."""
        self._suppress_finished = True
        self._player.stop()

    def reset(self) -> None:
        # Clear current file before stop() so a synchronous EndOfMedia cannot
        # request a file id from the previous block.
        self._suppress_finished = True
        self._current = None
        self._files = []
        self._player.stop()
        self._player.setSource(QUrl())
        self._now.setText("No audio selected")
        self._error.setText("")

    def _toggle_play(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _nudge(self, delta: int) -> None:
        self._player.setPosition(max(0, self._player.position() + delta))

    def _seek_released(self) -> None:
        self._player.setPosition(self._seek.value())
        self._seeking = False

    def _on_position(self, position: int) -> None:
        if not self._seeking:
            self._seek.setValue(position)
        self._elapsed.setText(format_position(position))

    def _on_duration(self, duration: int) -> None:
        self._seek.setRange(0, max(0, duration))
        self._remaining.setText(format_position(duration))

    def _on_state(self, state: QMediaPlayer.PlaybackState) -> None:
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self._play.setText("Pause" if playing else "Play")

    def _on_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status in (
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
        ):
            self._suppress_finished = False
            return
        if status != QMediaPlayer.MediaStatus.EndOfMedia:
            return
        if self._suppress_finished or self._current is None:
            return
        duration = self._player.duration()
        position = self._player.position()
        if duration <= 0 or position < max(0, duration - 250):
            return
        self._play_next()

    def _on_error(self, *_args: object) -> None:
        message = self._player.errorString() or "Audio playback failed."
        self._error.setText(message)

    def _apply_speed(self) -> None:
        rate = float(self._speed.currentData() or 1.0)
        self._player.setPlaybackRate(rate)

    def _apply_volume(self, value: int) -> None:
        volume = value / 100.0
        if not self._mute.isChecked():
            self._unmuted_volume = volume
        self._audio.setVolume(volume)

    def _apply_mute(self, muted: bool) -> None:
        self._audio.setMuted(muted)
        self._mute.setText("Unmute" if muted else "Mute")

    def _play_next(self) -> None:
        if self._current is None:
            return
        nxt = next_audio(self._files, self._current.id)
        if nxt is None:
            self.stop()
            return
        self.requestFile.emit(nxt.id)

    def _play_previous(self) -> None:
        if self._current is None:
            return
        prev = previous_audio(self._files, self._current.id)
        if prev is None:
            self._player.setPosition(0)
            return
        self.requestFile.emit(prev.id)
