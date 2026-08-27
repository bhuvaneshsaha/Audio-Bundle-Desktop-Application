from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from audio_bundle.core.models.node import NodeType
from audio_bundle.shared.constants import MAX_FOLDER_DEPTH
from audio_bundle.shared.errors import ValidationError


def folder_depth(folders: Sequence[Any], folder_id: str | None) -> int:
    """Root folders are depth 1. ``None`` (project root) is depth 0."""
    if folder_id is None:
        return 0
    by_id = {folder.id: folder for folder in folders}
    depth = 0
    current: str | None = folder_id
    seen: set[str] = set()
    while current is not None:
        if current in seen:
            raise ValidationError("Folder hierarchy contains a cycle.", code="folder_cycle")
        seen.add(current)
        folder = by_id.get(current)
        if folder is None:
            raise ValidationError("Folder parent was not found.", code="invalid_parent")
        depth += 1
        if depth > MAX_FOLDER_DEPTH:
            raise ValidationError(
                "This course uses a single folder level (Day 1, Day 2, …).",
                code="folder_depth",
            )
        current = folder.parent_id
    return depth


def children_of(folders: Sequence[Any], blocks: Sequence[Any], parent_id: str | None) -> list[Any]:
    nodes: list[Any] = [folder for folder in folders if folder.parent_id == parent_id]
    nodes.extend(block for block in blocks if block.parent_id == parent_id)
    nodes.sort(key=lambda node: (node.order, node.id))
    return nodes


def sibling_blocks(blocks: Sequence[Any], parent_id: str | None) -> list[Any]:
    siblings = [block for block in blocks if block.parent_id == parent_id]
    siblings.sort(key=lambda block: (block.order, block.id))
    return siblings


def _is_folder(node: Any) -> bool:
    kind = getattr(node, "node_type", None)
    return kind is NodeType.FOLDER or kind == NodeType.FOLDER or str(kind) == "folder"


def walk_tree(
    folders: Sequence[Any],
    blocks: Sequence[Any],
    parent_id: str | None = None,
) -> Iterator[tuple[NodeType, Any]]:
    for node in children_of(folders, blocks, parent_id):
        if _is_folder(node):
            yield NodeType.FOLDER, node
            yield from walk_tree(folders, blocks, node.id)
        else:
            yield NodeType.BLOCK, node


def blocks_in_tree_order(folders: Sequence[Any], blocks: Sequence[Any]) -> list[Any]:
    return [node for kind, node in walk_tree(folders, blocks) if kind is NodeType.BLOCK]


def renumber_siblings(folders: list[Any], blocks: list[Any], parent_id: str | None) -> None:
    for index, node in enumerate(children_of(folders, blocks, parent_id)):
        node.order = index


def next_root_folder_name(folders: Sequence[Any], *, sequence: int) -> str:
    """Default root names are Day N. The label has no sequencing meaning."""
    existing = {folder.name for folder in folders if folder.parent_id is None}
    number = max(sequence, 1)
    while f"Day {number}" in existing:
        number += 1
    return f"Day {number}"


def next_nested_folder_name(folders: Sequence[Any], parent_id: str | None) -> str:
    used: set[int] = set()
    prefix = "Folder "
    for folder in folders:
        if folder.parent_id != parent_id:
            continue
        if folder.name.startswith(prefix) and folder.name[len(prefix) :].isdigit():
            used.add(int(folder.name[len(prefix) :]))
    number = 1
    while number in used:
        number += 1
    return f"{prefix}{number}"
