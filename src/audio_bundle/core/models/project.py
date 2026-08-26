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
from audio_bundle.core.models.folder import Folder
from audio_bundle.core.models.tree import (
    blocks_in_tree_order,
    children_of,
    folder_depth,
    next_nested_folder_name,
    next_root_folder_name,
    renumber_siblings,
    sibling_blocks,
    walk_tree,
)
from audio_bundle.core.validation.fields import parse_datetime, require_non_empty_name
from audio_bundle.core.validation.project import validate_project_graph
from audio_bundle.shared.constants import MAX_FOLDER_DEPTH, PROJECT_SCHEMA_VERSION
from audio_bundle.shared.errors import ValidationError
from audio_bundle.shared.utilities import isoformat_utc, new_id, utc_now


@dataclass(slots=True)
class Project:
    """Editable admin project. Distinct from a generated .audiobundle file."""

    name: str
    id: str = field(default_factory=new_id)
    schema_version: int = PROJECT_SCHEMA_VERSION
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    folders: list[Folder] = field(default_factory=list)
    blocks: list[Block] = field(default_factory=list)
    autoplay_on_open: bool = False
    single_active_block: bool = True
    sequential_unlock: bool = True
    block_auth_method: BlockAuthMethod = BlockAuthMethod.PASSWORD
    windows_principals: list[str] = field(default_factory=list)
    root_folder_seq: int = 0

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
        if not isinstance(self.root_folder_seq, int) or self.root_folder_seq < 0:
            raise ValidationError("Root folder sequence is invalid.", code="invalid_order")
        for parent_id in {None, *[folder.id for folder in self.folders]}:
            renumber_siblings(self.folders, self.blocks, parent_id)
        for block in self.blocks:
            block.auth_method = self.block_auth_method
            block.windows_principals = list(self.windows_principals)
        validate_project_graph(self)

    def touch(self) -> None:
        self.updated_at = utc_now()

    def children(self, parent_id: str | None) -> list[Folder | Block]:
        return children_of(self.folders, self.blocks, parent_id)

    def sibling_blocks(self, parent_id: str | None) -> list[Block]:
        return sibling_blocks(self.blocks, parent_id)

    def walk(self):
        return walk_tree(self.folders, self.blocks)

    def get_folder(self, folder_id: str) -> Folder:
        for folder in self.folders:
            if folder.id == folder_id:
                return folder
        raise ValidationError("Folder not found in this project.", code="folder_not_found")

    def folder_depth_of(self, folder_id: str | None) -> int:
        return folder_depth(self.folders, folder_id)

    def _assert_folder_parent(self, parent_id: str | None, *, for_folder: bool) -> None:
        if parent_id is None:
            return
        self.get_folder(parent_id)
        depth = folder_depth(self.folders, parent_id)
        if for_folder and depth >= MAX_FOLDER_DEPTH:
            raise ValidationError(
                f"Folders may be nested at most {MAX_FOLDER_DEPTH} levels.",
                code="folder_depth",
            )

    def add_folder(self, folder: Folder, *, index: int | None = None) -> Folder:
        self._assert_folder_parent(folder.parent_id, for_folder=True)
        siblings = self.children(folder.parent_id)
        if index is None:
            folder.order = len(siblings)
        else:
            if index < 0 or index > len(siblings):
                raise ValidationError("Invalid insert index.", code="invalid_index")
            folder.order = index
        self.folders.append(folder)
        renumber_siblings(self.folders, self.blocks, folder.parent_id)
        validate_project_graph(self)
        self.touch()
        return folder

    def add_block(self, block: Block, *, index: int | None = None) -> Block:
        self._assert_folder_parent(block.parent_id, for_folder=False)
        siblings = self.children(block.parent_id)
        if index is None:
            block.order = len(siblings)
        else:
            if index < 0 or index > len(siblings):
                raise ValidationError("Invalid insert index.", code="invalid_index")
            block.order = index
        self.blocks.append(block)
        block.auth_method = self.block_auth_method
        block.windows_principals = list(self.windows_principals)
        renumber_siblings(self.folders, self.blocks, block.parent_id)
        validate_project_graph(self)
        self.touch()
        return block

    def remove_block(self, block_id: str) -> Block:
        for index, block in enumerate(self.blocks):
            if block.id == block_id:
                removed = self.blocks.pop(index)
                renumber_siblings(self.folders, self.blocks, removed.parent_id)
                self.touch()
                return removed
        raise ValidationError("Block not found in this project.", code="block_not_found")

    def descendant_folder_ids(self, folder_id: str) -> list[str]:
        ids = [folder_id]
        changed = True
        while changed:
            changed = False
            for folder in self.folders:
                if folder.parent_id in ids and folder.id not in ids:
                    ids.append(folder.id)
                    changed = True
        return ids

    def remove_folder(self, folder_id: str) -> tuple[Folder, list[Block]]:
        ids = set(self.descendant_folder_ids(folder_id))
        folder = self.get_folder(folder_id)
        parent_id = folder.parent_id
        removed_blocks = [block for block in self.blocks if block.parent_id in ids]
        self.blocks = [block for block in self.blocks if block.parent_id not in ids]
        self.folders = [item for item in self.folders if item.id not in ids]
        renumber_siblings(self.folders, self.blocks, parent_id)
        validate_project_graph(self)
        self.touch()
        return folder, removed_blocks

    def move_block(self, from_index: int, to_index: int) -> None:
        """Reorder among the sibling block list of ``blocks[from_index]``.

        When every block shares one parent and there are no folders, indexes are
        the global ``blocks`` list (legacy Admin / tests).
        """
        if from_index < 0 or from_index >= len(self.blocks):
            raise ValidationError("Invalid source index.", code="invalid_index")
        if to_index < 0 or to_index >= len(self.blocks):
            raise ValidationError("Invalid destination index.", code="invalid_index")
        parent_id = self.blocks[from_index].parent_id
        if not self.folders and all(block.parent_id == parent_id for block in self.blocks):
            block = self.blocks.pop(from_index)
            self.blocks.insert(to_index, block)
            for index, item in enumerate(self.blocks):
                item.order = index
            self.touch()
            return
        siblings = self.sibling_blocks(parent_id)
        source = next(i for i, block in enumerate(siblings) if block.id == self.blocks[from_index].id)
        dest = min(to_index, len(siblings) - 1)
        block = siblings.pop(source)
        siblings.insert(dest, block)
        self.reorder_siblings(parent_id, [item.id for item in siblings])

    def reorder_siblings(self, parent_id: str | None, ordered_ids: list[str]) -> None:
        current = [node.id for node in self.children(parent_id)]
        block_only = [block.id for block in self.sibling_blocks(parent_id)]
        if set(ordered_ids) == set(block_only) and len(ordered_ids) == len(block_only):
            folder_ids = [folder.id for folder in self.folders if folder.parent_id == parent_id]
            folder_ids.sort(key=lambda folder_id: self.get_folder(folder_id).order)
            ordered_ids = folder_ids + list(ordered_ids)
        if set(ordered_ids) != set(current) or len(ordered_ids) != len(current):
            raise ValidationError("Node list is inconsistent.", code="invalid_order")
        by_id = {node.id: node for node in self.children(parent_id)}
        for index, node_id in enumerate(ordered_ids):
            by_id[node_id].order = index
        if not self.folders and all(block.parent_id == parent_id for block in self.blocks):
            mapping = {block.id: block for block in self.blocks}
            self.blocks = [mapping[node_id] for node_id in ordered_ids]
        self.touch()

    def move_node(self, node_id: str, *, delta: int) -> None:
        parent_id = None
        if any(folder.id == node_id for folder in self.folders):
            parent_id = self.get_folder(node_id).parent_id
        else:
            parent_id = self.get_block(node_id).parent_id
        ids = [node.id for node in self.children(parent_id)]
        index = ids.index(node_id)
        dest = index + delta
        if dest < 0 or dest >= len(ids):
            return
        ids[index], ids[dest] = ids[dest], ids[index]
        self.reorder_siblings(parent_id, ids)
        validate_project_graph(self)

    def get_block(self, block_id: str) -> Block:
        for block in self.blocks:
            if block.id == block_id:
                return block
        raise ValidationError("Block not found in this project.", code="block_not_found")

    def default_root_folder_name(self) -> str:
        return next_root_folder_name(self.folders, sequence=self.root_folder_seq + 1)

    def default_nested_folder_name(self, parent_id: str | None) -> str:
        return next_nested_folder_name(self.folders, parent_id)

    def to_dict(self) -> dict[str, Any]:
        ordered_blocks = blocks_in_tree_order(self.folders, self.blocks)
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "name": self.name,
            "created_at": isoformat_utc(self.created_at),
            "updated_at": isoformat_utc(self.updated_at),
            "autoplay_on_open": self.autoplay_on_open,
            "single_active_block": self.single_active_block,
            "sequential_unlock": self.sequential_unlock,
            "block_auth_method": str(self.block_auth_method),
            "windows_principals": list(self.windows_principals),
            "root_folder_seq": self.root_folder_seq,
            "folders": [folder.to_dict() for folder in self.folders],
            "blocks": [block.to_dict() for block in ordered_blocks or self.blocks],
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
        folders = [Folder.from_dict(raw) for raw in raw_folders]
        blocks = [Block.from_dict(raw) for raw in raw_blocks]
        auth_method = payload.get("block_auth_method")
        if auth_method is None and blocks:
            auth_method = blocks[0].auth_method
        principals = payload.get("windows_principals")
        if principals is None and blocks:
            principals = blocks[0].windows_principals
        created_at = payload.get("created_at")
        updated_at = payload.get("updated_at")
        root_folder_seq = int(payload.get("root_folder_seq", 0))
        if root_folder_seq == 0:
            root_folder_seq = sum(1 for folder in folders if folder.parent_id is None)
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
            root_folder_seq=root_folder_seq,
        )
