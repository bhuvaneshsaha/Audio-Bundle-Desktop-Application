from __future__ import annotations

from pathlib import Path

import pytest

from audio_bundle.core.auth.hello import _raise_from_hello_output
from audio_bundle.core.auth.identity import WindowsIdentity, principal_allowed
from audio_bundle.core.auth.windows import DevelopmentAuthenticator, parse_account
from audio_bundle.core.bundle.session import ClientSession
from audio_bundle.core.crypto import CryptoEngine, KdfProfile
from audio_bundle.core.models import BlockAuthMethod
from audio_bundle.core.models.project import Project
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
        return WindowsIdentity(username=self.username, domain=self.domain, groups=self.groups)


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


def test_hello_output_verified() -> None:
    _raise_from_hello_output("AVAIL:Available\nRESULT:Verified")


def test_hello_output_device_not_present() -> None:
    with pytest.raises(AuthenticationError) as exc:
        _raise_from_hello_output("AVAIL:DeviceNotPresent")
    assert exc.value.code == "hello_unavailable"


def test_legacy_project_infers_global_windows_auth() -> None:
    project = Project.from_dict(
        {
            "name": "Legacy",
            "blocks": [
                {
                    "name": "Lesson",
                    "order": 0,
                    "auth_method": "windows",
                    "windows_principals": [r"SCHOOL\alice"],
                    "items": [],
                }
            ],
        }
    )
    assert project.block_auth_method is BlockAuthMethod.WINDOWS
    assert project.windows_principals == [r"SCHOOL\alice"]
    assert project.blocks[0].auth_method is BlockAuthMethod.WINDOWS
    serialized = project.to_dict()
    assert serialized["block_auth_method"] == "windows"
    assert "auth_method" not in serialized["blocks"][0]


def test_global_windows_blocks(tmp_path: Path) -> None:
    workspace = ProjectWorkspace.create(tmp_path, "Auth Course")
    first = workspace.add_block("Open")
    second = workspace.add_block("Next")
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"audio")
    workspace.import_files(first.id, [audio])
    workspace.import_files(second.id, [audio])
    workspace.set_block_auth_method(BlockAuthMethod.WINDOWS, windows_principals=[r"SCHOOL\alice"])
    workspace.set_sequential_unlock(True)
    workspace.set_single_active_block(True)
    bundle = tmp_path / "course.audiobundle"
    workspace.generate_bundle(bundle, main_password="main", engine=_engine())

    session = ClientSession.open(bundle, "main")
    assert session.opened.manifest.block_auth_method is BlockAuthMethod.WINDOWS
    assert session.opened.manifest.blocks[0].auth_method is BlockAuthMethod.WINDOWS
    assert session.opened.manifest.blocks[1].auth_method is BlockAuthMethod.WINDOWS
    with pytest.raises(BundleError) as exc:
        session.unlock_block(second.id, authenticator=FakeWindows())
    assert exc.value.code == "sequential_block_required"

    with pytest.raises(AuthenticationError):
        session.unlock_block(
            first.id,
            windows_username=r"SCHOOL\alice",
            windows_password="wrong",
            authenticator=FakeWindows(),
        )
    session.unlock_block(
        first.id,
        windows_username=r"SCHOOL\alice",
        windows_password="correct",
        authenticator=FakeWindows(),
    )
    assert session.is_unlocked(first.id)

    session.unlock_block(
        second.id,
        windows_identity=WindowsIdentity(username="alice", domain="SCHOOL"),
        authenticator=FakeWindows(),
    )
    assert session.is_unlocked(second.id)
    assert not session.is_unlocked(first.id)
    session.close()


def test_global_none_blocks(tmp_path: Path) -> None:
    workspace = ProjectWorkspace.create(tmp_path, "Open")
    first = workspace.add_block("Free")
    second = workspace.add_block("Also free")
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"x")
    workspace.import_files(first.id, [audio])
    workspace.import_files(second.id, [audio])
    workspace.set_block_auth_method(BlockAuthMethod.NONE)
    workspace.set_sequential_unlock(False)
    workspace.set_single_active_block(False)
    bundle = tmp_path / "open.audiobundle"
    workspace.generate_bundle(bundle, main_password="main", block_passwords={}, engine=_engine())
    session = ClientSession.open(bundle, "main")
    session.unlock_block(first.id)
    session.unlock_block(second.id)
    assert session.is_unlocked(first.id)
    assert session.is_unlocked(second.id)
    assert session.block_contents(first.id).files
    session.close()


def test_password_blocks_still_need_passwords(tmp_path: Path) -> None:
    workspace = ProjectWorkspace.create(tmp_path, "Secret")
    first = workspace.add_block("One")
    second = workspace.add_block("Two")
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"audio")
    workspace.import_files(first.id, [audio])
    workspace.import_files(second.id, [audio])
    workspace.set_block_password(first.id, "alpha")
    workspace.set_block_password(second.id, "beta")
    workspace.set_sequential_unlock(True)
    workspace.set_single_active_block(True)
    bundle = tmp_path / "secret.audiobundle"
    workspace.generate_bundle(bundle, main_password="main", engine=_engine())
    session = ClientSession.open(bundle, "main")
    session.unlock_block(first.id, "alpha")
    session.unlock_block(second.id, "beta")
    assert session.is_unlocked(second.id)
    assert not session.is_unlocked(first.id)
    session.close()


def test_development_authenticator_requires_fields() -> None:
    auth = DevelopmentAuthenticator()
    with pytest.raises(AuthenticationError):
        auth.verify_password("", "")
    identity = auth.verify_password(r"LAB\student", "pw")
    assert identity.username == "student"
    assert identity.domain == "LAB"
    with pytest.raises(AuthenticationError) as exc:
        auth.verify_hello()
    assert exc.value.code == "hello_unavailable"
