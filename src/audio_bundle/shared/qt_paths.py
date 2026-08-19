from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths


def _settings(app: str) -> QSettings:
    return QSettings("Audio Bundle", app)


def documents_dir() -> str:
    location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    if location:
        return location
    return str(Path.home())


def last_dir(app: str, key: str, fallback: str | None = None) -> str:
    stored = str(_settings(app).value(key, "") or "")
    if stored:
        path = Path(stored)
        if path.is_file():
            path = path.parent
        if path.is_dir():
            return str(path)
    if fallback and Path(fallback).is_dir():
        return fallback
    return documents_dir()


def remember_path(app: str, key: str, path: str) -> None:
    if not path:
        return
    candidate = Path(path)
    directory = candidate.parent if candidate.suffix else candidate
    if directory.is_file():
        directory = directory.parent
    if directory.is_dir():
        _settings(app).setValue(key, str(directory))
