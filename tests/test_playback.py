from __future__ import annotations

from audio_bundle.core.models.manifest import BundleFileEntry
from audio_bundle.core.playback import audio_entries, format_position, next_audio, previous_audio


def _file(name: str, media: str, file_id: str) -> BundleFileEntry:
    return BundleFileEntry(
        id=file_id,
        display_name=name,
        original_filename=name,
        media_type=media,
        order=0,
    )


def test_format_position() -> None:
    assert format_position(0) == "00:00"
    assert format_position(42_000) == "00:42"
    assert format_position(12 * 60_000 + 31_000) == "12:31"
    assert format_position(3_661_000) == "1:01:01"


def test_sequential_audio_skips_pdf() -> None:
    files = [
        _file("01 Introduction.mp3", "audio", "a"),
        _file("notes.pdf", "pdf", "p"),
        _file("02 Lesson.mp3", "audio", "b"),
        _file("03 Example.mp3", "audio", "c"),
    ]
    assert [item.id for item in audio_entries(files)] == ["a", "b", "c"]
    assert next_audio(files, "a").id == "b"
    assert next_audio(files, "b").id == "c"
    assert next_audio(files, "c") is None
    assert previous_audio(files, "c").id == "b"
    assert previous_audio(files, "b").id == "a"
    assert previous_audio(files, "a") is None
    assert next_audio(files, "p") is None
