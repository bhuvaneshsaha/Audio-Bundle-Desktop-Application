from __future__ import annotations

from pathlib import Path

from audio_bundle.core.auth.identity import WindowsIdentity, principal_allowed
from audio_bundle.core.auth.windows import default_authenticator
from audio_bundle.core.bundle.reader import OpenedBundle, UnlockedBlock, open_bundle
from audio_bundle.core.models.auth_method import BlockAuthMethod
from audio_bundle.core.models.manifest import BundleBlockContents, BundleFileEntry
from audio_bundle.core.storage.temp_content import TemporaryContentStore
from audio_bundle.shared.errors import AuthenticationError, BundleError


class ClientSession:
    """Opened bundle plus unlocked blocks and short-lived decrypted files."""

    def __init__(self, opened: OpenedBundle, store: TemporaryContentStore | None = None) -> None:
        self.opened = opened
        self._unlocked: dict[str, UnlockedBlock] = {}
        self._opened_once: set[str] = set()
        self._store = store or TemporaryContentStore()
        self._materialized: dict[tuple[str, str], Path] = {}

    @classmethod
    def open(cls, path: Path, main_password: str) -> ClientSession:
        return cls(open_bundle(path, main_password))

    @property
    def title(self) -> str:
        return self.opened.manifest.title

    def is_unlocked(self, block_id: str) -> bool:
        return block_id in self._unlocked

    def was_opened(self, block_id: str) -> bool:
        return block_id in self._opened_once

    def is_sequence_locked(self, block_id: str) -> bool:
        try:
            self.ensure_can_unlock(block_id)
        except BundleError as exc:
            return exc.code == "sequential_block_required"
        return False

    def ensure_can_unlock(self, block_id: str) -> None:
        self.block_summary(block_id)
        if block_id not in self._unlocked:
            self._assert_sequential(block_id)

    def block_summary(self, block_id: str):
        for block in self.opened.manifest.blocks:
            if block.id == block_id:
                return block
        raise BundleError("Block not found in this bundle.", code="block_not_found")

    def unlock_block(
        self,
        block_id: str,
        password: str = "",
        *,
        windows_username: str = "",
        windows_password: str = "",
        windows_identity: WindowsIdentity | None = None,
        authenticator: object | None = None,
    ) -> UnlockedBlock:
        if block_id in self._unlocked:
            return self._unlocked[block_id]
        self._assert_sequential(block_id)
        method = self.opened.manifest.block_auth_method
        principals = self.opened.manifest.windows_principals
        if method is BlockAuthMethod.WINDOWS:
            auth = authenticator or default_authenticator()
            if windows_identity is not None:
                identity = windows_identity
            else:
                identity = auth.verify_password(windows_username, windows_password)  # type: ignore[union-attr]
            if not isinstance(identity, WindowsIdentity):
                raise AuthenticationError("Windows authentication failed.", code="windows_logon_failed")
            if not principal_allowed(identity, principals):
                raise AuthenticationError(
                    "This Windows account is not allowed to open this block.",
                    code="windows_principal_denied",
                )
            unlocked = self.opened.unlock_block(block_id, None)
        elif method is BlockAuthMethod.NONE:
            unlocked = self.opened.unlock_block(block_id, None)
        else:
            unlocked = self.opened.unlock_block(block_id, password)
        if self.opened.manifest.single_active_block:
            for other_id in list(self._unlocked):
                if other_id != block_id:
                    self.lock_block(other_id)
        self._unlocked[block_id] = unlocked
        self._opened_once.add(block_id)
        return unlocked

    def lock_block(self, block_id: str) -> None:
        self._unlocked.pop(block_id, None)
        for key in [item for item in self._materialized if item[0] == block_id]:
            path = self._materialized.pop(key)
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    def _assert_sequential(self, block_id: str) -> None:
        if not self.opened.manifest.sequential_unlock:
            return
        from audio_bundle.core.models.tree import sibling_blocks

        summary = self.block_summary(block_id)
        siblings = sibling_blocks(self.opened.manifest.blocks, summary.parent_id)
        index = next(i for i, block in enumerate(siblings) if block.id == block_id)
        for previous in siblings[:index]:
            if previous.id not in self._opened_once:
                raise BundleError(
                    f"Open “{previous.name}” before this block.",
                    code="sequential_block_required",
                )

    def block_contents(self, block_id: str) -> BundleBlockContents:
        if block_id not in self._unlocked:
            raise BundleError("This block is still locked.", code="block_locked")
        return self._unlocked[block_id].contents

    def materialize_file(self, block_id: str, file_id: str) -> tuple[BundleFileEntry, Path]:
        key = (block_id, file_id)
        if block_id not in self._unlocked:
            raise BundleError("This block is still locked.", code="block_locked")
        unlocked = self._unlocked[block_id]
        entry = next((item for item in unlocked.contents.files if item.id == file_id), None)
        if entry is None:
            raise BundleError("File not found in this block.", code="item_not_found")
        if key not in self._materialized or not self._materialized[key].is_file():
            plaintext = unlocked.read_file(file_id)
            self._materialized[key] = self._store.write(entry.original_filename, plaintext)
        return entry, self._materialized[key]

    def close(self) -> None:
        self._unlocked.clear()
        self._opened_once.clear()
        self._materialized.clear()
        self._store.cleanup()
