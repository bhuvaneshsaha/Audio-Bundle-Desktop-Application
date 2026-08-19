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
