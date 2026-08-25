from __future__ import annotations

from collections.abc import Sequence

from audio_bundle.shared.constants import MAX_BLOCKS_PER_PROJECT, MAX_FOLDERS_PER_PROJECT, MAX_ITEMS_PER_BLOCK
from audio_bundle.shared.errors import ValidationError


def _unique_ids(ids: Sequence[str], *, kind: str) -> None:
    seen: set[str] = set()
    for item_id in ids:
        if item_id in seen:
            raise ValidationError(f"Duplicate {kind} id: {item_id}", code="duplicate_id")
        seen.add(item_id)


def validate_block_graph(block: object) -> None:
    from audio_bundle.core.models.block import Block

    if not isinstance(block, Block):
        raise ValidationError("Expected a Block model.", code="invalid_block")
    if len(block.items) > MAX_ITEMS_PER_BLOCK:
        raise ValidationError(
            f"A block may contain at most {MAX_ITEMS_PER_BLOCK} files.",
            code="too_many_items",
        )
    _unique_ids([item.id for item in block.items], kind="file")
    orders = [item.order for item in block.items]
    if orders != list(range(len(block.items))):
        raise ValidationError("File order indexes must be contiguous starting at 0.", code="invalid_order")


def validate_project_graph(project: object) -> None:
    from audio_bundle.core.models.project import Project

    if not isinstance(project, Project):
        raise ValidationError("Expected a Project model.", code="invalid_project")
    if len(project.blocks) > MAX_BLOCKS_PER_PROJECT:
        raise ValidationError(
            f"A project may contain at most {MAX_BLOCKS_PER_PROJECT} blocks.",
            code="too_many_blocks",
        )
    if len(project.folders) > MAX_FOLDERS_PER_PROJECT:
        raise ValidationError(
            f"A project may contain at most {MAX_FOLDERS_PER_PROJECT} folders.",
            code="too_many_folders",
        )
    _unique_ids([folder.id for folder in project.folders], kind="folder")
    by_id = {folder.id: folder for folder in project.folders}
    for folder in project.folders:
        if folder.parent_id is not None and folder.parent_id not in by_id:
            raise ValidationError("Folder parent does not exist.", code="invalid_folder_parent")
        seen: set[str] = set()
        cursor = folder.parent_id
        while cursor is not None:
            if cursor == folder.id or cursor in seen:
                raise ValidationError("Folder hierarchy contains a cycle.", code="invalid_folder_parent")
            seen.add(cursor)
            cursor = by_id[cursor].parent_id if cursor in by_id else None
    for parent_id in {folder.parent_id for folder in project.folders} | {None}:
        siblings = sorted(
            [folder for folder in project.folders if folder.parent_id == parent_id],
            key=lambda folder: folder.order,
        )
        orders = [folder.order for folder in siblings]
        if orders != list(range(len(siblings))):
            raise ValidationError("Folder order indexes must be contiguous starting at 0.", code="invalid_order")
    _unique_ids([block.id for block in project.blocks], kind="block")
    all_item_ids: list[str] = []
    for block in project.blocks:
        if block.folder_id is None:
            raise ValidationError("Every block must belong to a folder.", code="missing_folder")
        if block.folder_id not in by_id:
            raise ValidationError("Block points to an unknown folder.", code="invalid_folder")
        validate_block_graph(block)
        all_item_ids.extend(item.id for item in block.items)
    _unique_ids(all_item_ids, kind="file")
    orders = [block.order for block in project.blocks]
    if orders != list(range(len(project.blocks))):
        raise ValidationError("Block order indexes must be contiguous starting at 0.", code="invalid_order")
