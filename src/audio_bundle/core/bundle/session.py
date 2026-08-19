from __future__ import annotations

from pathlib import Path

from audio_bundle.core.bundle.reader import OpenedBundle, UnlockedBlock, open_bundle
from audio_bundle.core.models.manifest import BundleBlockContents, BundleFileEntry
from audio_bundle.core.storage.temp_content import TemporaryContentStore
from audio_bundle.shared.errors import BundleError


class ClientSession:
    """Opened bundle plus unlocked blocks and short-lived decrypted files."""

    def __init__(self, opened: OpenedBundle, store: TemporaryContentStore | None = None) -> None:
        self.opened = opened
        self._unlocked: dict[str, UnlockedBlock] = {}
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

    def unlock_block(self, block_id: str, password: str) -> UnlockedBlock:
        if block_id in self._unlocked:
            return self._unlocked[block_id]
        unlocked = self.opened.unlock_block(block_id, password)
        self._unlocked[block_id] = unlocked
        return unlocked

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
        self._materialized.clear()
        self._store.cleanup()
