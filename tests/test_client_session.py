from __future__ import annotations

from pathlib import Path

import pytest

from audio_bundle.core.bundle.session import ClientSession
from audio_bundle.core.crypto import CryptoEngine, KdfProfile
from audio_bundle.core.storage.workspace import ProjectWorkspace
from audio_bundle.shared.errors import AuthenticationError, BundleError


def _engine() -> CryptoEngine:
    return CryptoEngine(kdf_profile=KdfProfile.TEST)


def _make_bundle(tmp_path: Path) -> tuple[Path, str, dict[str, str]]:
    workspace = ProjectWorkspace.create(tmp_path, "Client Course")
    intro = workspace.add_block("Introduction")
    audio = tmp_path / "welcome.mp3"
    pdf = tmp_path / "notes.pdf"
    audio.write_bytes(b"audio-bytes")
    pdf.write_bytes(b"%PDF-notes")
    workspace.import_files(intro.id, [audio, pdf])
    passwords = {intro.id: "block-secret"}
    bundle = tmp_path / "course.audiobundle"
    workspace.generate_bundle(
        bundle,
        main_password="main-secret",
        block_passwords=passwords,
        engine=_engine(),
    )
    return bundle, intro.id, passwords


def test_client_session_main_and_block_passwords(tmp_path: Path) -> None:
    bundle, block_id, passwords = _make_bundle(tmp_path)
    with pytest.raises(AuthenticationError):
        ClientSession.open(bundle, "wrong-main")
    session = ClientSession.open(bundle, "main-secret")
    assert session.title == "Client Course"
    assert not session.is_unlocked(block_id)
    with pytest.raises(AuthenticationError):
        session.unlock_block(block_id, "nope")
    session.unlock_block(block_id, passwords[block_id])
    names = [entry.display_name for entry in session.block_contents(block_id).files]
    assert names == ["welcome", "notes"]
    assert session.opened.manifest.autoplay_on_open is False
    entry, path = session.materialize_file(block_id, session.block_contents(block_id).files[0].id)
    assert entry.media_type.value == "audio"
    assert path.read_bytes() == b"audio-bytes"
    assert path.is_relative_to(session._store.root)
    root = session._store.root
    session.close()
    assert not root.exists()


def test_client_session_does_not_materialize_while_locked(tmp_path: Path) -> None:
    bundle, block_id, _passwords = _make_bundle(tmp_path)
    session = ClientSession.open(bundle, "main-secret")
    with pytest.raises(BundleError) as exc:
        session.materialize_file(block_id, "missing")
    assert exc.value.code == "block_locked"
    session.close()


def test_sequential_unlock_checks_folders_then_blocks(tmp_path: Path) -> None:
    workspace = ProjectWorkspace.create(tmp_path, "Sequence")
    day1 = workspace.add_day_folder("Day 1")
    day2 = workspace.add_day_folder("Day 2")
    day1_intro = workspace.add_block("Intro", folder_id=day1.id)
    day1_next = workspace.add_block("Part 2", folder_id=day1.id)
    day2_intro = workspace.add_block("Day2 Intro", folder_id=day2.id)
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"audio")
    workspace.import_files(day1_intro.id, [audio])
    workspace.import_files(day1_next.id, [audio])
    workspace.import_files(day2_intro.id, [audio])
    passwords = {
        day1_intro.id: "p1",
        day1_next.id: "p2",
        day2_intro.id: "p3",
    }
    bundle = tmp_path / "sequence.audiobundle"
    workspace.generate_bundle(bundle, main_password="main", block_passwords=passwords, engine=_engine())
    session = ClientSession.open(bundle, "main")
    with pytest.raises(BundleError) as intra:
        session.unlock_block(day1_next.id, "p2")
    assert intra.value.code == "sequential_block_required"
    with pytest.raises(BundleError) as exc:
        session.unlock_block(day2_intro.id, "p3")
    assert exc.value.code == "sequential_block_required"
    session.unlock_block(day1_intro.id, "p1")
    session.unlock_block(day2_intro.id, "p3")
    session.close()
