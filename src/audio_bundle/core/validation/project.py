from __future__ import annotations

from collections.abc import Sequence

from audio_bundle.core.models.tree import children_of, folder_depth
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
    folder_ids = [folder.id for folder in project.folders]
    block_ids = [block.id for block in project.blocks]
    _unique_ids(folder_ids + block_ids, kind="node")
    folder_id_set = set(folder_ids)
    for folder in project.folders:
        if folder.parent_id is not None and folder.parent_id not in folder_id_set:
            raise ValidationError("Folder parent was not found.", code="invalid_parent")
        if folder.parent_id == folder.id:
            raise ValidationError("Folder hierarchy contains a cycle.", code="folder_cycle")
        folder_depth(project.folders, folder.id)
    for block in project.blocks:
        if block.parent_id is not None and block.parent_id not in folder_id_set:
            raise ValidationError("Block parent was not found.", code="invalid_parent")
        validate_block_graph(block)
    all_item_ids: list[str] = []
    for block in project.blocks:
        all_item_ids.extend(item.id for item in block.items)
    _unique_ids(all_item_ids, kind="file")
    parents = {None, *folder_ids}
    for parent_id in parents:
        siblings = children_of(project.folders, project.blocks, parent_id)
        orders = [node.order for node in siblings]
        if orders != list(range(len(siblings))):
            raise ValidationError(
                "Sibling order indexes must be contiguous starting at 0.",
                code="invalid_order",
            )
