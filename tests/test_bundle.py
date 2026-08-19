from __future__ import annotations

import zlib
from pathlib import Path
from zipfile import ZipFile

import pytest

from audio_bundle.core.bundle import open_bundle, write_bundle
from audio_bundle.core.bundle.format import HEADER_SIZE, parse_container
from audio_bundle.core.crypto import KdfProfile
from audio_bundle.core.crypto.engine import CryptoEngine
from audio_bundle.core.models import Block, MediaItem, Project
from audio_bundle.shared.constants import BUNDLE_FORMAT_VERSION
from audio_bundle.shared.errors import AuthenticationError, BundleError, CryptoError, ValidationError


def _engine() -> CryptoEngine:
    return CryptoEngine(kdf_profile=KdfProfile.TEST)


def _item(filename: str, relative: str, display: str | None = None) -> MediaItem:
    return MediaItem.from_import(
        original_filename=filename,
        relative_source_path=relative,
        display_name=display or filename,
    )


def _write_sources(root: Path) -> Project:
    (root / "blocks" / "intro").mkdir(parents=True)
    (root / "blocks" / "lesson").mkdir(parents=True)
    (root / "blocks" / "intro" / "welcome.mp3").write_bytes(b"ID3-welcome-audio")
    (root / "blocks" / "intro" / "syllabus.pdf").write_bytes(b"%PDF-1.4 syllabus")
    (root / "blocks" / "lesson" / "lesson.wav").write_bytes(b"RIFF-lesson-audio")

    project = Project(name="Sample Course")
    intro = project.add_block(Block(name="Introduction"))
    intro.add_item(_item("welcome.mp3", "blocks/intro/welcome.mp3", "Welcome audio"))
    intro.add_item(_item("syllabus.pdf", "blocks/intro/syllabus.pdf", "Syllabus"))
    lesson = project.add_block(Block(name="Lesson 1"))
    lesson.add_item(_item("lesson.wav", "blocks/lesson/lesson.wav", "Lesson audio"))
    project.add_block(Block(name="Exercises"))
    return project


def _passwords(project: Project) -> dict[str, str]:
    mapping = {
        "Introduction": "intro-secret",
        "Lesson 1": "lesson-secret",
        "Exercises": "exercise-secret",
    }
    return {block.id: mapping[block.name] for block in project.blocks}


def test_write_and_read_bundle_roundtrip(tmp_path: Path) -> None:
    project = _write_sources(tmp_path)
    bundle_path = tmp_path / "course.audiobundle"
    write_bundle(
        project,
        bundle_path,
        main_password="main-secret",
        block_passwords=_passwords(project),
        source_root=tmp_path,
        engine=_engine(),
    )

    opened = open_bundle(bundle_path, "main-secret")
    assert opened.manifest.title == "Sample Course"
    assert [block.name for block in opened.manifest.blocks] == [
        "Introduction",
        "Lesson 1",
        "Exercises",
    ]
    raw = bundle_path.read_bytes()
    assert b"Welcome audio" not in raw
    assert b"welcome.mp3" not in raw
    assert b"ID3-welcome-audio" not in raw

    intro = opened.unlock_block(opened.manifest.blocks[0].id, "intro-secret")
    assert [entry.display_name for entry in intro.contents.files] == ["Welcome audio", "Syllabus"]
    assert [entry.original_filename for entry in intro.contents.files] == ["welcome.mp3", "syllabus.pdf"]
    assert intro.read_file(intro.contents.files[0].id) == b"ID3-welcome-audio"
    assert intro.read_file(intro.contents.files[1].id) == b"%PDF-1.4 syllabus"
    assert [entry.original_filename for entry in intro.contents.ordered_audio_files()] == ["welcome.mp3"]

    lesson = opened.unlock_block(opened.manifest.blocks[1].id, "lesson-secret")
    assert lesson.read_file_at(0) == b"RIFF-lesson-audio"

    empty = opened.unlock_block(opened.manifest.blocks[2].id, "exercise-secret")
    assert empty.contents.files == []


def test_wrong_main_password(tmp_path: Path) -> None:
    project = _write_sources(tmp_path)
    bundle_path = tmp_path / "course.audiobundle"
    write_bundle(
        project,
        bundle_path,
        main_password="main-secret",
        block_passwords=_passwords(project),
        source_root=tmp_path,
        engine=_engine(),
    )
    with pytest.raises(AuthenticationError) as exc:
        open_bundle(bundle_path, "nope")
    assert exc.value.code == "wrong_password"


def test_wrong_block_password(tmp_path: Path) -> None:
    project = _write_sources(tmp_path)
    bundle_path = tmp_path / "course.audiobundle"
    write_bundle(
        project,
        bundle_path,
        main_password="main-secret",
        block_passwords=_passwords(project),
        source_root=tmp_path,
        engine=_engine(),
    )
    opened = open_bundle(bundle_path, "main-secret")
    with pytest.raises(AuthenticationError) as exc:
        opened.unlock_block(opened.manifest.blocks[0].id, "lesson-secret")
    assert exc.value.code == "wrong_password"


def test_file_order_is_admin_order_not_alphabetical(tmp_path: Path) -> None:
    (tmp_path / "blocks").mkdir()
    (tmp_path / "blocks" / "zeta.mp3").write_bytes(b"zeta")
    (tmp_path / "blocks" / "alpha.mp3").write_bytes(b"alpha")
    project = Project(name="Order")
    block = project.add_block(Block(name="Mix"))
    block.add_item(_item("zeta.mp3", "blocks/zeta.mp3"))
    block.add_item(_item("alpha.mp3", "blocks/alpha.mp3"))
    path = tmp_path / "order.audiobundle"
    write_bundle(
        project,
        path,
        main_password="m",
        block_passwords={block.id: "b"},
        source_root=tmp_path,
        engine=_engine(),
    )
    opened = open_bundle(path, "m")
    unlocked = opened.unlock_block(block.id, "b")
    assert [entry.original_filename for entry in unlocked.contents.files] == ["zeta.mp3", "alpha.mp3"]
    assert unlocked.read_file_at(0) == b"zeta"
    assert unlocked.read_file_at(1) == b"alpha"


def test_empty_block_and_missing_source(tmp_path: Path) -> None:
    project = Project(name="Empty")
    block = project.add_block(Block(name="Only"))
    path = tmp_path / "empty.audiobundle"
    write_bundle(
        project,
        path,
        main_password="m",
        block_passwords={block.id: "b"},
        source_root=tmp_path,
        engine=_engine(),
    )
    opened = open_bundle(path, "m")
    assert opened.unlock_block(block.id, "b").contents.files == []

    project2 = Project(name="Missing")
    missing = project2.add_block(Block(name="Files"))
    missing.add_item(_item("gone.mp3", "blocks/gone.mp3"))
    with pytest.raises(BundleError) as exc:
        write_bundle(
            project2,
            tmp_path / "missing.audiobundle",
            main_password="m",
            block_passwords={missing.id: "b"},
            source_root=tmp_path,
            engine=_engine(),
        )
    assert exc.value.code == "missing_source_file"


def test_large_file_roundtrip(tmp_path: Path) -> None:
    payload = bytes((i * 17) % 256 for i in range(512 * 1024))
    (tmp_path / "blocks").mkdir()
    (tmp_path / "blocks" / "big.mp3").write_bytes(payload)
    project = Project(name="Large")
    block = project.add_block(Block(name="Big"))
    block.add_item(_item("big.mp3", "blocks/big.mp3"))
    path = tmp_path / "large.audiobundle"
    write_bundle(
        project,
        path,
        main_password="m",
        block_passwords={block.id: "b"},
        source_root=tmp_path,
        engine=_engine(),
    )
    unlocked = open_bundle(path, "m").unlock_block(block.id, "b")
    assert unlocked.read_file_at(0) == payload


def test_corrupted_ciphertext_is_detected(tmp_path: Path) -> None:
    project = _write_sources(tmp_path)
    path = tmp_path / "course.audiobundle"
    write_bundle(
        project,
        path,
        main_password="main-secret",
        block_passwords=_passwords(project),
        source_root=tmp_path,
        engine=_engine(),
    )
    data = bytearray(path.read_bytes())
    data[HEADER_SIZE + 80] ^= 0x5A
    path.write_bytes(data)
    with pytest.raises((AuthenticationError, BundleError, CryptoError)):
        opened = open_bundle(path, "main-secret")
        opened.unlock_block(opened.manifest.blocks[0].id, "intro-secret")


def test_truncated_bundle(tmp_path: Path) -> None:
    project = _write_sources(tmp_path)
    path = tmp_path / "course.audiobundle"
    write_bundle(
        project,
        path,
        main_password="main-secret",
        block_passwords=_passwords(project),
        source_root=tmp_path,
        engine=_engine(),
    )
    data = path.read_bytes()
    path.write_bytes(data[:-20])
    with pytest.raises(BundleError) as exc:
        open_bundle(path, "main-secret")
    assert exc.value.code == "truncated_bundle"


def test_unsupported_version(tmp_path: Path) -> None:
    project = _write_sources(tmp_path)
    path = tmp_path / "course.audiobundle"
    write_bundle(
        project,
        path,
        main_password="main-secret",
        block_passwords=_passwords(project),
        source_root=tmp_path,
        engine=_engine(),
    )
    data = bytearray(path.read_bytes())
    data[16:18] = (BUNDLE_FORMAT_VERSION + 1).to_bytes(2, "little")
    crc = zlib.crc32(data[:20]) & 0xFFFFFFFF
    data[20:24] = crc.to_bytes(4, "little")
    path.write_bytes(data)
    with pytest.raises(BundleError) as exc:
        open_bundle(path, "main-secret")
    assert exc.value.code == "unsupported_bundle_version"


def test_zip_file_is_rejected(tmp_path: Path) -> None:
    zip_path = tmp_path / "fake.audiobundle"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr("readme.txt", "not a bundle")
    with pytest.raises(BundleError) as exc:
        open_bundle(zip_path, "x")
    assert exc.value.code == "zip_not_supported"


def test_header_crc_mismatch(tmp_path: Path) -> None:
    project = _write_sources(tmp_path)
    path = tmp_path / "course.audiobundle"
    write_bundle(
        project,
        path,
        main_password="main-secret",
        block_passwords=_passwords(project),
        source_root=tmp_path,
        engine=_engine(),
    )
    data = bytearray(path.read_bytes())
    data[20] ^= 0x01
    path.write_bytes(data)
    with pytest.raises(BundleError) as exc:
        parse_container(bytes(data))
    assert exc.value.code == "header_checksum_mismatch"


def test_missing_block_password_refused(tmp_path: Path) -> None:
    project = _write_sources(tmp_path)
    with pytest.raises(ValidationError) as exc:
        write_bundle(
            project,
            tmp_path / "out.audiobundle",
            main_password="main",
            block_passwords={},
            source_root=tmp_path,
            engine=_engine(),
        )
    assert exc.value.code == "missing_block_password"
