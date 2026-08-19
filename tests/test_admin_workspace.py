from __future__ import annotations

import json
from pathlib import Path

import pytest

from audio_bundle.core.bundle import open_bundle
from audio_bundle.core.crypto import CryptoEngine, KdfProfile
from audio_bundle.core.storage.workspace import ProjectWorkspace
from audio_bundle.shared.errors import BundleError, ValidationError


def _engine() -> CryptoEngine:
    return CryptoEngine(kdf_profile=KdfProfile.TEST)


def test_create_save_reload_and_generate(tmp_path: Path) -> None:
    workspace = ProjectWorkspace.create(tmp_path, "Demo Course")
    assert workspace.project_file.is_file()
    intro = workspace.add_block("Introduction")
    lesson = workspace.add_block("Lesson 1")
    audio = tmp_path / "welcome.mp3"
    pdf = tmp_path / "notes.pdf"
    extra = tmp_path / "zeta.mp3"
    audio.write_bytes(b"audio-one")
    pdf.write_bytes(b"%PDF-demo")
    extra.write_bytes(b"audio-two")
    workspace.import_files(intro.id, [audio, pdf])
    workspace.import_files(lesson.id, [extra])
    workspace.rename_item(intro.id, workspace.project.blocks[0].items[0].id, "Welcome")
    workspace.reorder_items(intro.id, [workspace.project.blocks[0].items[1].id, workspace.project.blocks[0].items[0].id])
    workspace.reorder_blocks([lesson.id, intro.id])
    workspace.save()

    reloaded = ProjectWorkspace.open(workspace.project_file)
    assert reloaded.project.name == "Demo Course"
    assert [block.name for block in reloaded.project.blocks] == ["Lesson 1", "Introduction"]
    intro_files = reloaded.project.blocks[1].items
    assert [item.display_name for item in intro_files] == ["notes", "Welcome"]
    assert [item.original_filename for item in intro_files] == ["notes.pdf", "welcome.mp3"]

    removed_id = intro_files[0].id
    reloaded.remove_item(reloaded.project.blocks[1].id, removed_id)
    reloaded.save()

    passwords = {block.id: f"pw-{block.name}" for block in reloaded.project.blocks}
    bundle_path = reloaded.default_bundle_path()
    reloaded.generate_bundle(
        bundle_path,
        main_password="main-secret",
        block_passwords=passwords,
        engine=_engine(),
    )
    payload = json.loads(reloaded.project_file.read_text(encoding="utf-8"))
    assert "password" not in json.dumps(payload).lower()
    opened = open_bundle(bundle_path, "main-secret")
    assert [block.name for block in opened.manifest.blocks] == ["Lesson 1", "Introduction"]
    block = next(block for block in opened.manifest.blocks if block.name == "Introduction")
    unlocked = opened.unlock_block(block.id, "pw-Introduction")
    assert [entry.display_name for entry in unlocked.contents.files] == ["Welcome"]
    assert unlocked.read_file_at(0) == b"audio-one"


def test_import_rejects_unsupported_type(tmp_path: Path) -> None:
    workspace = ProjectWorkspace.create(tmp_path, "Types")
    block = workspace.add_block("A")
    bad = tmp_path / "payload.exe"
    bad.write_bytes(b"MZ")
    with pytest.raises(ValidationError) as exc:
        workspace.import_files(block.id, [bad])
    assert exc.value.code == "unsupported_file_type"


def test_duplicate_project_folder_rejected(tmp_path: Path) -> None:
    ProjectWorkspace.create(tmp_path, "Same")
    with pytest.raises(BundleError) as exc:
        ProjectWorkspace.create(tmp_path, "Same")
    assert exc.value.code == "project_exists"
