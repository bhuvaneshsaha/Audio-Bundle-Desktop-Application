from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from audio_bundle.core.models import (
    Block,
    BundleBlockContents,
    BundleManifest,
    MediaItem,
    MediaType,
    Project,
)
from audio_bundle.core.storage import load_project, save_project
from audio_bundle.core.validation.fields import assert_no_secret_fields
from audio_bundle.shared.errors import ValidationError


def _audio(name: str, order: int = 0, folder: str = "blocks/block-001") -> MediaItem:
    return MediaItem.from_import(
        original_filename=name,
        relative_source_path=f"{folder}/{name}",
        display_name=name,
        order=order,
        size_bytes=1024,
    )


def _pdf(name: str, order: int = 0, folder: str = "blocks/block-001") -> MediaItem:
    return MediaItem.from_import(
        original_filename=name,
        relative_source_path=f"{folder}/{name}",
        display_name=name,
        order=order,
        size_bytes=2048,
    )


def test_media_type_from_filename() -> None:
    assert MediaType.from_filename("lesson.mp3") is MediaType.AUDIO
    assert MediaType.from_filename("notes.PDF") is MediaType.PDF
    assert MediaType.from_filename("clip.m4a").is_playable_audio()
    with pytest.raises(ValidationError) as exc:
        MediaType.from_filename("malware.exe")
    assert exc.value.code == "unsupported_file_type"


def test_media_item_rejects_path_traversal() -> None:
    with pytest.raises(ValidationError) as exc:
        MediaItem.from_import(
            original_filename="a.mp3",
            relative_source_path="../secret.mp3",
        )
    assert exc.value.code == "path_traversal"


def test_media_item_rejects_absolute_path() -> None:
    with pytest.raises(ValidationError):
        MediaItem.from_import(original_filename="a.mp3", relative_source_path="/etc/passwd")
    with pytest.raises(ValidationError):
        MediaItem.from_import(original_filename="a.mp3", relative_source_path="C:/windows/a.mp3")


def test_media_item_type_mismatch() -> None:
    with pytest.raises(ValidationError) as exc:
        MediaItem(
            display_name="x",
            original_filename="a.mp3",
            relative_source_path="blocks/a.mp3",
            media_type=MediaType.PDF,
        )
    assert exc.value.code == "media_type_mismatch"


def test_block_reorder_is_not_alphabetical() -> None:
    block = Block(name="Lesson 1")
    block.add_item(_audio("zeta.mp3"))
    block.add_item(_audio("alpha.mp3"))
    block.add_item(_pdf("omega.pdf"))
    assert [item.original_filename for item in block.items] == ["zeta.mp3", "alpha.mp3", "omega.pdf"]
    block.move_item(2, 0)
    assert [item.original_filename for item in block.items] == ["omega.pdf", "zeta.mp3", "alpha.mp3"]
    assert [item.order for item in block.items] == [0, 1, 2]


def test_block_remove_and_rename() -> None:
    block = Block(name="Intro")
    first = block.add_item(_audio("a.mp3"))
    block.add_item(_audio("b.mp3"))
    block.rename_item(first.id, "Opening audio")
    assert block.items[0].display_name == "Opening audio"
    block.remove_item(first.id)
    assert [item.original_filename for item in block.items] == ["b.mp3"]
    assert block.items[0].order == 0


def test_empty_block_is_allowed() -> None:
    block = Block(name="Placeholder")
    assert block.items == []
    project = Project(name="Course")
    project.add_block(block)
    restored = Project.from_dict(project.to_dict())
    assert restored.blocks[0].items == []


def test_project_block_reorder_and_roundtrip(tmp_path: Path) -> None:
    project = Project(name="Course")
    project.add_block(Block(name="Block C"))
    project.add_block(Block(name="Block A"))
    project.add_block(Block(name="Block B"))
    project.move_block(0, 2)
    assert [block.name for block in project.blocks] == ["Block A", "Block B", "Block C"]

    intro = project.get_block(project.blocks[0].id)
    intro.add_item(_audio("02 Lesson.mp3", folder="blocks/block-a"))
    intro.add_item(_audio("01 Introduction.mp3", folder="blocks/block-a"))
    intro.move_item(1, 0)

    path = tmp_path / "project.json"
    save_project(project, path)
    loaded = load_project(path)
    assert loaded.name == "Course"
    assert [block.name for block in loaded.blocks] == ["Block A", "Block B", "Block C"]
    assert [item.original_filename for item in loaded.blocks[0].items] == [
        "01 Introduction.mp3",
        "02 Lesson.mp3",
    ]


def test_duplicate_file_ids_rejected() -> None:
    item = _audio("a.mp3")
    clone = deepcopy(item)
    with pytest.raises(ValidationError) as exc:
        Block(name="Dup", items=[item, clone])
    assert exc.value.code == "duplicate_id"


def test_unsupported_project_schema() -> None:
    payload = Project(name="x").to_dict()
    payload["schema_version"] = 99
    with pytest.raises(ValidationError) as exc:
        Project.from_dict(payload)
    assert exc.value.code == "unsupported_schema_version"


def test_project_json_never_contains_password_fields(tmp_path: Path) -> None:
    project = Project(name="Secure Course")
    block = project.add_block(Block(name="Intro"))
    block.add_item(_audio("a.mp3"))
    path = tmp_path / "project.json"
    save_project(project, path)
    text = path.read_text(encoding="utf-8").lower()
    assert "password" not in text
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert_no_secret_fields(payload)


def test_load_project_rejects_embedded_password(tmp_path: Path) -> None:
    project = Project(name="x")
    project.add_block(Block(name="Intro"))
    payload = project.to_dict()
    payload["blocks"][0]["password"] = "hunter2"
    path = tmp_path / "project.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValidationError) as exc:
        load_project(path)
    assert exc.value.code == "secret_field_forbidden"


def test_outer_manifest_hides_file_list() -> None:
    project = Project(name="Course")
    block = project.add_block(Block(name="Lesson 1"))
    block.add_item(_audio("hidden.mp3"))
    manifest = BundleManifest.from_project(project)
    serialized = manifest.to_dict()
    assert "hidden.mp3" not in json.dumps(serialized)
    assert serialized["blocks"][0]["name"] == "Lesson 1"
    assert "files" not in serialized["blocks"][0]
    restored = BundleManifest.from_dict(serialized)
    assert restored.title == "Course"
    assert restored.blocks[0].id == block.id


def test_inner_manifest_preserves_order_and_skips_pdf_in_audio_list() -> None:
    block = Block(name="Mixed")
    block.add_item(_audio("a.mp3"))
    block.add_item(_pdf("sheet.pdf"))
    block.add_item(_audio("b.wav"))
    contents = BundleBlockContents.from_block(block)
    assert [entry.original_filename for entry in contents.files] == ["a.mp3", "sheet.pdf", "b.wav"]
    assert [entry.original_filename for entry in contents.ordered_audio_files()] == ["a.mp3", "b.wav"]
    roundtrip = BundleBlockContents.from_dict(contents.to_dict())
    assert [entry.original_filename for entry in roundtrip.files] == ["a.mp3", "sheet.pdf", "b.wav"]


def test_unsupported_bundle_version() -> None:
    payload = BundleManifest(title="Course").to_dict()
    payload["format_version"] = 2
    with pytest.raises(ValidationError) as exc:
        BundleManifest.from_dict(payload)
    assert exc.value.code == "unsupported_bundle_version"


def test_sample_admin_project_loads() -> None:
    sample = Path(__file__).resolve().parents[1] / "samples" / "admin_project" / "project.json"
    project = load_project(sample)
    assert project.name == "Sample Course"
    assert [block.name for block in project.blocks] == [
        "Introduction",
        "Lesson 1",
        "Exercises",
    ]
    intro_names = [item.display_name for item in project.blocks[0].items]
    assert intro_names == ["Welcome audio", "Syllabus"]
    assert project.blocks[2].items == []
