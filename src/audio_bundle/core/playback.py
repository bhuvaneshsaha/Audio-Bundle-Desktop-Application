from __future__ import annotations

from audio_bundle.core.models.manifest import BundleFileEntry


PLAYBACK_SPEEDS = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0)
SEEK_STEP_MS = 10_000


def format_position(milliseconds: int) -> str:
    total_seconds = max(0, milliseconds) // 1000
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def audio_entries(files: list[BundleFileEntry]) -> list[BundleFileEntry]:
    return [entry for entry in files if entry.media_type.is_playable_audio()]


def _index(files: list[BundleFileEntry], file_id: str) -> int | None:
    for index, entry in enumerate(files):
        if entry.id == file_id:
            return index
    return None


def next_audio(files: list[BundleFileEntry], file_id: str) -> BundleFileEntry | None:
    queue = audio_entries(files)
    index = _index(queue, file_id)
    if index is None or index + 1 >= len(queue):
        return None
    return queue[index + 1]


def previous_audio(files: list[BundleFileEntry], file_id: str) -> BundleFileEntry | None:
    queue = audio_entries(files)
    index = _index(queue, file_id)
    if index is None or index <= 0:
        return None
    return queue[index - 1]
