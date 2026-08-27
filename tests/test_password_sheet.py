from __future__ import annotations

from pathlib import Path

from audio_bundle.core.bundle.password_sheet import password_sheet_path, render_password_sheet
from audio_bundle.core.crypto import CryptoEngine, KdfProfile
from audio_bundle.core.models import BlockAuthMethod
from audio_bundle.core.storage.workspace import ProjectWorkspace


def _engine() -> CryptoEngine:
    return CryptoEngine(kdf_profile=KdfProfile.TEST)


def test_password_sheet_path() -> None:
    assert password_sheet_path(Path("/tmp/Course.audiobundle")) == Path("/tmp/Course-passwords.txt")


def test_generate_writes_shareable_password_file(tmp_path: Path) -> None:
    workspace = ProjectWorkspace.create(tmp_path, "Share Course")
    day1 = workspace.add_folder()
    day2 = workspace.add_folder()
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"x")
    intro = workspace.add_block("Introduction", parent_id=day1.id)
    next_block = workspace.add_block("Block 1", parent_id=day2.id)
    workspace.import_files(intro.id, [audio])
    workspace.import_files(next_block.id, [audio])
    workspace.set_block_password(intro.id, "intro-pw")
    workspace.set_block_password(next_block.id, "day2-pw")
    bundle = tmp_path / "Share_Course.audiobundle"
    workspace.generate_bundle(bundle, main_password="course-main", engine=_engine())
    sheet = password_sheet_path(bundle)
    assert sheet.is_file()
    text = sheet.read_text(encoding="utf-8")
    assert "course-main" in text
    assert "intro-pw" in text
    assert "day2-pw" in text
    assert "Day 1" in text
    assert "Day 2" in text
    assert "Introduction" in text
    project_text = workspace.project_file.read_text(encoding="utf-8")
    assert "course-main" not in project_text
    assert "intro-pw" not in project_text


def test_windows_sheet_has_main_password_only(tmp_path: Path) -> None:
    workspace = ProjectWorkspace.create(tmp_path, "Win")
    block = workspace.add_block("Open")
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"x")
    workspace.import_files(block.id, [audio])
    workspace.set_block_auth_method(BlockAuthMethod.WINDOWS)
    text = render_password_sheet(
        workspace.project,
        bundle_filename="Win.audiobundle",
        main_password="main-only",
        block_passwords={},
    )
    assert "main-only" in text
    assert "Windows authentication" in text
    assert "Open" in text
    assert "Block passwords" not in text
