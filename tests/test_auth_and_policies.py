from __future__ import annotations

from pathlib import Path

import pytest

from audio_bundle.core.auth.identity import WindowsIdentity, principal_allowed
from audio_bundle.core.auth.windows import DevelopmentAuthenticator, parse_account
from audio_bundle.core.bundle.session import ClientSession
from audio_bundle.core.crypto import CryptoEngine, KdfProfile
from audio_bundle.core.models import BlockAuthMethod
from audio_bundle.core.storage.workspace import ProjectWorkspace
from audio_bundle.shared.errors import AuthenticationError, BundleError


def _engine() -> CryptoEngine:
    return CryptoEngine(kdf_profile=KdfProfile.TEST)


class FakeWindows:
    def __init__(self, *, username: str = "alice", domain: str = "SCHOOL", groups: tuple[str, ...] = ()) -> None:
        self.username = username
        self.domain = domain
        self.groups = groups

    def verify_password(self, username: str, password: str) -> WindowsIdentity:
        if password != "correct":
            raise AuthenticationError("Windows user name or password is incorrect.", code="windows_logon_failed")
        return WindowsIdentity(username=self.username, domain=self.domain, groups=self.groups)

    def verify_hello(self) -> WindowsIdentity:
        raise AuthenticationError("Hello unavailable", code="hello_unavailable")


def test_principal_allowlist() -> None:
    identity = WindowsIdentity(username="alice", domain="SCHOOL", upn="alice@school.local", groups=("SCHOOL\\Students",))
    assert principal_allowed(identity, [])
    assert principal_allowed(identity, ["SCHOOL\\alice"])
    assert principal_allowed(identity, ["alice@school.local"])
    assert principal_allowed(identity, ["group:SCHOOL\\Students"])
    assert not principal_allowed(identity, ["SCHOOL\\bob"])


def test_parse_account() -> None:
    assert parse_account(r"SCHOOL\bob") == ("SCHOOL", "bob")
    assert parse_account("bob@school.local") == ("", "bob@school.local")
    assert parse_account("bob") == (".", "bob")


def test_none_and_windows_blocks(tmp_path: Path) -> None:
    workspace = ProjectWorkspace.create(tmp_path, "Auth Course")
    first = workspace.add_block("Open")
    second = workspace.add_block("Windows")
    third = workspace.add_block("Secret")
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"audio")
    workspace.import_files(first.id, [audio])
    workspace.import_files(second.id, [audio])
    workspace.import_files(third.id, [audio])
    workspace.set_block_auth(first.id, BlockAuthMethod.NONE)
    workspace.set_block_auth(second.id, BlockAuthMethod.WINDOWS, windows_principals=["SCHOOL\\alice"])
    workspace.set_block_password(third.id, "block-secret")
    workspace.set_sequential_unlock(True)
    workspace.set_single_active_block(True)
    bundle = tmp_path / "course.audiobundle"
    workspace.generate_bundle(bundle, main_password="main", engine=_engine())

    session = ClientSession.open(bundle, "main")
    assert session.opened.manifest.blocks[0].auth_method is BlockAuthMethod.NONE
    assert session.opened.manifest.blocks[1].auth_method is BlockAuthMethod.WINDOWS
    with pytest.raises(BundleError) as exc:
        session.unlock_block(second.id, authenticator=FakeWindows())
    assert exc.value.code == "sequential_block_required"

    session.unlock_block(first.id)
    assert session.is_unlocked(first.id)
    with pytest.raises(AuthenticationError):
        session.unlock_block(
            second.id,
            windows_username=r"SCHOOL\alice",
            windows_password="wrong",
            authenticator=FakeWindows(),
        )
    session.unlock_block(
        second.id,
        windows_username=r"SCHOOL\alice",
        windows_password="correct",
        authenticator=FakeWindows(),
    )
    assert session.is_unlocked(second.id)
    assert not session.is_unlocked(first.id)

    session.unlock_block(third.id, "block-secret")
    assert session.is_unlocked(third.id)
    assert not session.is_unlocked(second.id)
    session.close()


def test_generate_without_password_for_open_block(tmp_path: Path) -> None:
    workspace = ProjectWorkspace.create(tmp_path, "Open")
    block = workspace.add_block("Free")
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"x")
    workspace.import_files(block.id, [audio])
    workspace.set_block_auth(block.id, BlockAuthMethod.NONE)
    bundle = tmp_path / "open.audiobundle"
    workspace.generate_bundle(bundle, main_password="main", block_passwords={}, engine=_engine())
    session = ClientSession.open(bundle, "main")
    session.unlock_block(block.id)
    assert session.block_contents(block.id).files
    session.close()


def test_development_authenticator_requires_fields() -> None:
    auth = DevelopmentAuthenticator()
    with pytest.raises(AuthenticationError):
        auth.verify_password("", "")
    identity = auth.verify_password(r"LAB\student", "pw")
    assert identity.username == "student"
    assert identity.domain == "LAB"
