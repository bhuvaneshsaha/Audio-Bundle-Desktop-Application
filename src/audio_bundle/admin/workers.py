from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from audio_bundle.core.crypto.engine import CryptoEngine
from audio_bundle.core.storage.workspace import ProjectWorkspace
from audio_bundle.shared.messages import user_message

logger = logging.getLogger(__name__)


class ImportFilesWorker(QObject):
    finished = Signal(int)
    failed = Signal(str)

    def __init__(self, workspace: ProjectWorkspace, block_id: str, paths: list[Path]) -> None:
        super().__init__()
        self._workspace = workspace
        self._block_id = block_id
        self._paths = paths

    def run(self) -> None:
        try:
            imported = self._workspace.import_files(self._block_id, self._paths)
            self.finished.emit(len(imported))
        except Exception as exc:
            logger.exception("File import failed")
            self.failed.emit(user_message(exc))


class GenerateBundleWorker(QObject):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        workspace: ProjectWorkspace,
        output_path: Path,
        main_password: str,
        block_passwords: dict[str, str],
        engine: CryptoEngine | None = None,
    ) -> None:
        super().__init__()
        self._workspace = workspace
        self._output_path = output_path
        self._main_password = main_password
        self._block_passwords = block_passwords
        self._engine = engine

    def run(self) -> None:
        try:
            path = self._workspace.generate_bundle(
                self._output_path,
                main_password=self._main_password,
                block_passwords=self._block_passwords,
                engine=self._engine,
            )
            self.finished.emit(str(path))
        except Exception as exc:
            logger.exception("Bundle generation failed")
            self.failed.emit(user_message(exc))
