from __future__ import annotations

import shutil
from pathlib import Path

from audio_bundle.core.bundle.writer import write_bundle
from audio_bundle.core.crypto.engine import CryptoEngine
from audio_bundle.core.crypto.hashing import sha256_hex
from audio_bundle.core.models.block import Block
from audio_bundle.core.models.media_item import MediaItem
from audio_bundle.core.models.media_type import MediaType
from audio_bundle.core.models.project import Project
from audio_bundle.core.storage.project_store import load_project, save_project
from audio_bundle.core.validation.fields import require_non_empty_name
from audio_bundle.core.validation.project import validate_block_graph, validate_project_graph
from audio_bundle.shared.constants import BUNDLE_EXTENSION, MAX_FILENAME_LENGTH
from audio_bundle.shared.errors import BundleError, ValidationError
from audio_bundle.shared.utilities import new_id


def project_dir_name(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_ " else "-" for ch in name.strip())
    cleaned = " ".join(cleaned.split()) or "project"
    return cleaned[:80]


def unique_filename(directory: Path, filename: str) -> str:
    base = Path(filename).name
    if not base or base in {".", ".."}:
        raise ValidationError("Original filename is invalid.", code="invalid_filename")
    if len(base) > MAX_FILENAME_LENGTH:
        raise ValidationError("Original filename is too long.", code="filename_too_long")
    stem = Path(base).stem
    suffix = Path(base).suffix
    candidate = base
    n = 2
    while (directory / candidate).exists():
        candidate = f"{stem}-{n}{suffix}"
        n += 1
        if n > 10_000:
            raise BundleError("Could not find a unique filename.", code="filename_collision")
    return candidate


class ProjectWorkspace:
    """Admin project on disk. Passwords are never saved here."""

    def __init__(self, root: Path, project: Project) -> None:
        self.root = Path(root).resolve()
        self.project = project
        self.dirty = False
        self._block_passwords: dict[str, str] = {}

    @property
    def project_file(self) -> Path:
        return self.root / "project.json"

    @classmethod
    def create(cls, parent_dir: Path, name: str) -> ProjectWorkspace:
        parent = Path(parent_dir).resolve()
        parent.mkdir(parents=True, exist_ok=True)
        root = parent / project_dir_name(name)
        if root.exists():
            raise BundleError(
                "A folder with that project name already exists.",
                code="project_exists",
            )
        root.mkdir()
        (root / "blocks").mkdir()
        (root / "output").mkdir()
        workspace = cls(root, Project(name=name))
        workspace.save()
        return workspace

    @classmethod
    def open(cls, project_file: Path) -> ProjectWorkspace:
        path = Path(project_file).resolve()
        project = load_project(path)
        workspace = cls(path.parent, project)
        workspace.dirty = False
        return workspace

    def save(self) -> None:
        save_project(self.project, self.project_file)
        self.dirty = False

    def set_name(self, name: str) -> None:
        self.project.name = require_non_empty_name(name, field="Project name")
        self.project.touch()
        self.dirty = True

    def set_autoplay_on_open(self, enabled: bool) -> None:
        self.project.autoplay_on_open = bool(enabled)
        self.project.touch()
        self.dirty = True

    def set_single_active_block(self, enabled: bool) -> None:
        self.project.single_active_block = bool(enabled)
        self.project.touch()
        self.dirty = True

    def set_sequential_unlock(self, enabled: bool) -> None:
        self.project.sequential_unlock = bool(enabled)
        self.project.touch()
        self.dirty = True

    def set_block_auth_method(self, auth_method: object, *, windows_principals: list[str] | None = None) -> None:
        from audio_bundle.core.models.auth_method import parse_block_auth_method, parse_windows_principals

        self.project.block_auth_method = parse_block_auth_method(auth_method)
        if windows_principals is not None:
            self.project.windows_principals = parse_windows_principals(windows_principals)
        for block in self.project.blocks:
            block.auth_method = self.project.block_auth_method
            block.windows_principals = list(self.project.windows_principals)
        self.project.touch()
        self.dirty = True

    def next_block_name(self) -> str:
        used: set[int] = set()
        for block in self.project.blocks:
            prefix = "Block "
            if block.name.startswith(prefix):
                suffix = block.name[len(prefix) :]
                if suffix.isdigit():
                    used.add(int(suffix))
        number = 1
        while number in used:
            number += 1
        return f"Block {number}"

    def add_block(self, name: str | None = None) -> Block:
        block = Block(name=name or self.next_block_name(), id=new_id())
        self.project.add_block(block)
        (self.root / "blocks" / block.id).mkdir(parents=True, exist_ok=True)
        self.dirty = True
        return block

    def set_block_password(self, block_id: str, password: str) -> None:
        self.project.get_block(block_id)
        self._block_passwords[block_id] = password

    def block_password(self, block_id: str) -> str:
        return self._block_passwords.get(block_id, "")

    def session_block_passwords(self) -> dict[str, str]:
        return dict(self._block_passwords)

    def missing_password_block_names(self) -> list[str]:
        from audio_bundle.core.models.auth_method import BlockAuthMethod

        return [
            block.name
            for block in self.project.blocks
            if self.project.block_auth_method is BlockAuthMethod.PASSWORD and not self.block_password(block.id)
        ]

    def rename_block(self, block_id: str, name: str) -> Block:
        block = self.project.get_block(block_id)
        block.name = require_non_empty_name(name, field="Block name")
        self.project.touch()
        self.dirty = True
        return block

    def remove_block(self, block_id: str) -> None:
        self.project.remove_block(block_id)
        self._block_passwords.pop(block_id, None)
        folder = self.root / "blocks" / block_id
        if folder.exists():
            shutil.rmtree(folder)
        self.dirty = True

    def move_block(self, from_index: int, to_index: int) -> None:
        self.project.move_block(from_index, to_index)
        self.dirty = True

    def reorder_blocks(self, ordered_ids: list[str]) -> None:
        mapping = {block.id: block for block in self.project.blocks}
        if set(ordered_ids) != set(mapping) or len(ordered_ids) != len(mapping):
            raise ValidationError("Block list is inconsistent.", code="invalid_order")
        self.project.blocks = [mapping[block_id] for block_id in ordered_ids]
        for index, block in enumerate(self.project.blocks):
            block.order = index
        validate_project_graph(self.project)
        self.project.touch()
        self.dirty = True

    def import_files(self, block_id: str, source_paths: list[Path]) -> list[MediaItem]:
        block = self.project.get_block(block_id)
        dest_dir = self.root / "blocks" / block.id
        dest_dir.mkdir(parents=True, exist_ok=True)
        imported: list[MediaItem] = []
        for source in source_paths:
            path = Path(source)
            MediaType.from_filename(path.name)
            if not path.is_file():
                raise BundleError(f"Could not import '{path.name}'.", code="missing_source_file")
            filename = unique_filename(dest_dir, path.name)
            dest = dest_dir / filename
            try:
                shutil.copy2(path, dest)
            except OSError as exc:
                raise BundleError(f"Could not import '{path.name}'.", code="source_read_error") from exc
            data = dest.read_bytes()
            relative = dest.relative_to(self.root).as_posix()
            item = MediaItem.from_import(
                original_filename=path.name,
                relative_source_path=relative,
                display_name=path.stem or path.name,
                size_bytes=len(data),
                source_sha256=sha256_hex(data),
            )
            block.add_item(item)
            imported.append(item)
        self.project.touch()
        self.dirty = True
        return imported

    def remove_item(self, block_id: str, item_id: str) -> None:
        block = self.project.get_block(block_id)
        item = block.remove_item(item_id)
        file_path = (self.root / item.relative_source_path).resolve()
        if file_path.is_file() and file_path.is_relative_to(self.root):
            file_path.unlink(missing_ok=True)
        self.project.touch()
        self.dirty = True

    def rename_item(self, block_id: str, item_id: str, display_name: str) -> MediaItem:
        item = self.project.get_block(block_id).rename_item(item_id, display_name)
        self.project.touch()
        self.dirty = True
        return item

    def move_item(self, block_id: str, from_index: int, to_index: int) -> None:
        self.project.get_block(block_id).move_item(from_index, to_index)
        self.project.touch()
        self.dirty = True

    def reorder_items(self, block_id: str, ordered_ids: list[str]) -> None:
        block = self.project.get_block(block_id)
        mapping = {item.id: item for item in block.items}
        if set(ordered_ids) != set(mapping) or len(ordered_ids) != len(mapping):
            raise ValidationError("File list is inconsistent.", code="invalid_order")
        block.items = [mapping[item_id] for item_id in ordered_ids]
        for index, item in enumerate(block.items):
            item.order = index
        validate_block_graph(block)
        self.project.touch()
        self.dirty = True

    def default_bundle_path(self) -> Path:
        slug = project_dir_name(self.project.name).replace(" ", "_")
        return self.root / "output" / f"{slug}{BUNDLE_EXTENSION}"

    def generate_bundle(
        self,
        output_path: Path,
        *,
        main_password: str,
        block_passwords: dict[str, str] | None = None,
        engine: CryptoEngine | None = None,
    ) -> Path:
        if self.dirty:
            self.save()
        write_bundle(
            self.project,
            output_path,
            main_password=main_password,
            block_passwords=block_passwords if block_passwords is not None else self.session_block_passwords(),
            source_root=self.root,
            engine=engine,
        )
        return Path(output_path)
