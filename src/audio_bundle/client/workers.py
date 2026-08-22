from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from audio_bundle.core.bundle.session import ClientSession
from audio_bundle.core.models.manifest import BundleFileEntry
from audio_bundle.shared.messages import user_message

logger = logging.getLogger(__name__)


class OpenBundleWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, path: Path, password: str) -> None:
        super().__init__()
        self._path = path
        self._password = password

    def run(self) -> None:
        try:
            self.finished.emit(ClientSession.open(self._path, self._password))
        except Exception as exc:
            logger.exception("Opening bundle failed")
            self.failed.emit(user_message(exc))


class UnlockBlockWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        session: ClientSession,
        block_id: str,
        password: str = "",
        *,
        windows_username: str = "",
        windows_password: str = "",
        authenticator: object | None = None,
    ) -> None:
        super().__init__()
        self._session = session
        self._block_id = block_id
        self._password = password
        self._windows_username = windows_username
        self._windows_password = windows_password
        self._authenticator = authenticator

    def run(self) -> None:
        try:
            self.finished.emit(
                self._session.unlock_block(
                    self._block_id,
                    self._password,
                    windows_username=self._windows_username,
                    windows_password=self._windows_password,
                    authenticator=self._authenticator,
                )
            )
        except Exception as exc:
            logger.exception("Unlocking block failed")
            self.failed.emit(user_message(exc))


class DecryptFileWorker(QObject):
    finished = Signal(object, object)
    failed = Signal(str)

    def __init__(self, session: ClientSession, block_id: str, file_id: str) -> None:
        super().__init__()
        self._session = session
        self._block_id = block_id
        self._file_id = file_id

    def run(self) -> None:
        try:
            entry, path = self._session.materialize_file(self._block_id, self._file_id)
            self.finished.emit(entry, path)
        except Exception as exc:
            logger.exception("Decrypting file failed")
            self.failed.emit(user_message(exc))
