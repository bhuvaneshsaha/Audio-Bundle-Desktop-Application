from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from audio_bundle.core.models.auth_method import (
    BlockAuthMethod,
    parse_block_auth_method,
    parse_windows_principals,
)
from audio_bundle.core.models.block import Block
from audio_bundle.core.models.folder import ProjectFolder
from audio_bundle.core.validation.fields import parse_datetime, require_non_empty_name
from audio_bundle.core.validation.project import validate_project_graph
from audio_bundle.shared.constants import PROJECT_SCHEMA_VERSION
from audio_bundle.shared.errors import ValidationError
from audio_bundle.shared.utilities import isoformat_utc, new_id, utc_now


def _renumber(blocks: list[Block]) -> None:
    for index, block in enumerate(blocks):
        block.order = index


def _renumber_folders(folders: list[ProjectFolder], parent_id: str | None) -> None:
    siblings = [folder for folder in folders if folder.parent_id == parent_id]
    siblings.sort(key=lambda folder: folder.order)
    for index, folder in enumerate(siblings):
        folder.order = index


@dataclass(slots=True)
class Project:
    """Editable admin project. Distinct from a generated .audiobundle file."""

    name: str
    id: str = field(default_factory=new_id)
    schema_version: int = PROJECT_SCHEMA_VERSION
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    folders: list[ProjectFolder] = field(default_factory=list)
    blocks: list[Block] = field(default_factory=list)
    autoplay_on_open: bool = False
    single_active_block: bool = True
    sequential_unlock: bool = True
    block_auth_method: BlockAuthMethod = BlockAuthMethod.PASSWORD
    windows_principals: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.name = require_non_empty_name(self.name, field="Project name")
        if self.schema_version != PROJECT_SCHEMA_VERSION:
            raise ValidationError(
                f"Unsupported project schema version {self.schema_version}.",
                code="unsupported_schema_version",
            )
        if isinstance(self.block_auth_method, str):
            self.block_auth_method = parse_block_auth_method(self.block_auth_method)
        self.windows_principals = parse_windows_principals(self.windows_principals)
        self.folders.sort(key=lambda folder: (folder.parent_id or "", folder.order, folder.name.casefold()))
        for parent in {folder.parent_id for folder in self.folders} | {None}:
            _renumber_folders(self.folders, parent)
        _renumber(self.blocks)
        if not self.folders and self.blocks:
            self._seed_default_folders_for_blocks()
        for block in self.blocks:
            if block.folder_id is None:
                block.folder_id = self._ensure_default_folder_for_block(block.order).id
            block.auth_method = self.block_auth_method
            block.windows_principals = list(self.windows_principals)
        validate_project_graph(self)

    def touch(self) -> None:
        self.updated_at = utc_now()

    def add_folder(self, name: str, *, parent_id: str | None = None, index: int | None = None) -> ProjectFolder:
        if parent_id is not None:
            self.get_folder(parent_id)
        siblings = [folder for folder in self.folders if folder.parent_id == parent_id]
        if index is None:
            index = len(siblings)
        if index < 0 or index > len(siblings):
            raise ValidationError("Invalid insert index.", code="invalid_index")
        for folder in siblings:
            if folder.order >= index:
                folder.order += 1
        folder = ProjectFolder(name=name, parent_id=parent_id, order=index)
        self.folders.append(folder)
        _renumber_folders(self.folders, parent_id)
        validate_project_graph(self)
        self.touch()
        return folder

    def get_folder(self, folder_id: str) -> ProjectFolder:
        for folder in self.folders:
            if folder.id == folder_id:
                return folder
        raise ValidationError("Folder not found in this project.", code="folder_not_found")

    def rename_folder(self, folder_id: str, name: str) -> ProjectFolder:
        folder = self.get_folder(folder_id)
        folder.name = require_non_empty_name(name, field="Folder name")
        self.touch()
        return folder

    def move_folder(self, folder_id: str, parent_id: str | None, index: int | None = None) -> None:
        folder = self.get_folder(folder_id)
        if parent_id is not None:
            parent = self.get_folder(parent_id)
            lineage = {folder.id}
            cursor = parent.parent_id
            while cursor:
                if cursor in lineage:
                    raise ValidationError("Folder cannot be moved into itself.", code="invalid_folder_parent")
                lineage.add(cursor)
                cursor = self.get_folder(cursor).parent_id
        old_parent = folder.parent_id
        old_siblings = [item for item in self.folders if item.parent_id == old_parent and item.id != folder.id]
        new_siblings = [item for item in self.folders if item.parent_id == parent_id and item.id != folder.id]
        if index is None:
            index = len(new_siblings)
        if index < 0 or index > len(new_siblings):
            raise ValidationError("Invalid insert index.", code="invalid_index")
        for item in old_siblings:
            if item.order > folder.order:
                item.order -= 1
        folder.parent_id = parent_id
        folder.order = index
        for item in new_siblings:
            if item.order >= index:
                item.order += 1
        _renumber_folders(self.folders, old_parent)
        _renumber_folders(self.folders, parent_id)
        validate_project_graph(self)
        self.touch()

    def remove_folder(self, folder_id: str) -> ProjectFolder:
        folder = self.get_folder(folder_id)
        descendants = self._folder_descendants(folder.id)
        folder_ids = {folder.id, *descendants}
        for block in self.blocks:
            if block.folder_id in folder_ids:
                raise ValidationError(
                    "Move or remove blocks from this folder before deleting it.",
                    code="folder_not_empty",
                )
        self.folders = [item for item in self.folders if item.id not in folder_ids]
        _renumber_folders(self.folders, folder.parent_id)
        validate_project_graph(self)
        self.touch()
        return folder

    def folder_path(self, folder_id: str | None) -> list[str]:
        if folder_id is None:
            return []
        path: list[str] = []
        current = self.get_folder(folder_id)
        while True:
            path.append(current.name)
            if current.parent_id is None:
                break
            current = self.get_folder(current.parent_id)
        path.reverse()
        return path

    def add_block(self, block: Block, *, index: int | None = None, folder_id: str | None = None) -> Block:
        if index is None:
            self.blocks.append(block)
        else:
            if index < 0 or index > len(self.blocks):
                raise ValidationError("Invalid insert index.", code="invalid_index")
            self.blocks.insert(index, block)
        block.folder_id = folder_id or block.folder_id
        if block.folder_id is None:
            block.folder_id = self._ensure_default_folder_for_block(len(self.blocks) - 1).id
        else:
            self.get_folder(block.folder_id)
        block.auth_method = self.block_auth_method
        block.windows_principals = list(self.windows_principals)
        _renumber(self.blocks)
        validate_project_graph(self)
        self.touch()
        return block

    def remove_block(self, block_id: str) -> Block:
        for index, block in enumerate(self.blocks):
            if block.id == block_id:
                removed = self.blocks.pop(index)
                _renumber(self.blocks)
                self.touch()
                return removed
        raise ValidationError("Block not found in this project.", code="block_not_found")

    def move_block(self, from_index: int, to_index: int) -> None:
        if from_index < 0 or from_index >= len(self.blocks):
            raise ValidationError("Invalid source index.", code="invalid_index")
        if to_index < 0 or to_index >= len(self.blocks):
            raise ValidationError("Invalid destination index.", code="invalid_index")
        block = self.blocks.pop(from_index)
        self.blocks.insert(to_index, block)
        _renumber(self.blocks)
        self.touch()

    def assign_block_folder(self, block_id: str, folder_id: str) -> None:
        self.get_folder(folder_id)
        block = self.get_block(block_id)
        block.folder_id = folder_id
        self.touch()

    def get_block(self, block_id: str) -> Block:
        for block in self.blocks:
            if block.id == block_id:
                return block
        raise ValidationError("Block not found in this project.", code="block_not_found")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "name": self.name,
            "created_at": isoformat_utc(self.created_at),
            "updated_at": isoformat_utc(self.updated_at),
            "folders": [folder.to_dict() for folder in self.folders],
            "autoplay_on_open": self.autoplay_on_open,
            "single_active_block": self.single_active_block,
            "sequential_unlock": self.sequential_unlock,
            "block_auth_method": str(self.block_auth_method),
            "windows_principals": list(self.windows_principals),
            "blocks": [block.to_dict() for block in self.blocks],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Project:
        if not isinstance(payload, dict):
            raise ValidationError("Project must be an object.", code="invalid_project")
        if "name" not in payload:
            raise ValidationError("Project name is required.", code="missing_field")
        raw_blocks = payload.get("blocks", [])
        if not isinstance(raw_blocks, list):
            raise ValidationError("Project blocks must be a list.", code="invalid_blocks")
        raw_folders = payload.get("folders", [])
        if not isinstance(raw_folders, list):
            raise ValidationError("Project folders must be a list.", code="invalid_folders")
        folders = [ProjectFolder.from_dict(raw) for raw in raw_folders]
        blocks = [Block.from_dict(raw) for raw in raw_blocks]
        blocks.sort(key=lambda block: block.order)
        if not folders and blocks:
            for index, block in enumerate(blocks, start=1):
                folders.append(ProjectFolder(name=f"Day {index}", order=index - 1))
                block.folder_id = folders[-1].id
        auth_method = payload.get("block_auth_method")
        if auth_method is None and blocks:
            auth_method = blocks[0].auth_method
        principals = payload.get("windows_principals")
        if principals is None and blocks:
            principals = blocks[0].windows_principals
        created_at = payload.get("created_at")
        updated_at = payload.get("updated_at")
        return cls(
            id=str(payload["id"]) if "id" in payload else new_id(),
            name=payload["name"],
            schema_version=int(payload.get("schema_version", PROJECT_SCHEMA_VERSION)),
            created_at=parse_datetime(created_at, field="created_at") if created_at else utc_now(),
            updated_at=parse_datetime(updated_at, field="updated_at") if updated_at else utc_now(),
            folders=folders,
            blocks=blocks,
            autoplay_on_open=bool(payload.get("autoplay_on_open", False)),
            single_active_block=bool(payload.get("single_active_block", True)),
            sequential_unlock=bool(payload.get("sequential_unlock", True)),
            block_auth_method=parse_block_auth_method(auth_method),
            windows_principals=parse_windows_principals(principals),
        )

    def _seed_default_folders_for_blocks(self) -> None:
        self.folders = []
        for index, block in enumerate(self.blocks, start=1):
            folder = ProjectFolder(name=f"Day {index}", order=index - 1)
            self.folders.append(folder)
            block.folder_id = folder.id

    def _top_level_day_count(self) -> int:
        return len([folder for folder in self.folders if folder.parent_id is None])

    def _ensure_default_folder_for_block(self, block_order: int) -> ProjectFolder:
        desired = block_order + 1
        top = sorted(
            [folder for folder in self.folders if folder.parent_id is None],
            key=lambda folder: folder.order,
        )
        if desired <= len(top):
            return top[desired - 1]
        while len(top) < desired:
            folder = ProjectFolder(name=f"Day {len(top) + 1}", order=len(top))
            self.folders.append(folder)
            top.append(folder)
        return top[-1]

    def _folder_descendants(self, folder_id: str) -> list[str]:
        descendants: list[str] = []
        frontier = [folder_id]
        while frontier:
            current = frontier.pop()
            children = [folder.id for folder in self.folders if folder.parent_id == current]
            descendants.extend(children)
            frontier.extend(children)
        return descendants
