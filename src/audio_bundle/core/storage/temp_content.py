from __future__ import annotations

import os
import shutil
import stat
import tempfile
from pathlib import Path

from audio_bundle.core.validation.fields import suffix_for_filename
from audio_bundle.shared.utilities import new_id


class TemporaryContentStore:
    """Process-private directory for decrypted media. Not a user-visible export folder."""

    def __init__(self) -> None:
        self._root = Path(tempfile.mkdtemp(prefix="audiobundle-client-"))
        os.chmod(self._root, stat.S_IRWXU)

    @property
    def root(self) -> Path:
        return self._root

    def write(self, original_filename: str, data: bytes) -> Path:
        suffix = suffix_for_filename(original_filename)
        dest = self._root / f"{new_id()}{suffix}"
        dest.write_bytes(data)
        os.chmod(dest, stat.S_IRUSR | stat.S_IWUSR)
        return dest

    def cleanup(self) -> None:
        if self._root.exists():
            shutil.rmtree(self._root, ignore_errors=True)

    def __enter__(self) -> TemporaryContentStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.cleanup()
