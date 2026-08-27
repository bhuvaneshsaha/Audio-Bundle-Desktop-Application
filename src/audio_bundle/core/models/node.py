from __future__ import annotations

from enum import StrEnum

from audio_bundle.shared.errors import ValidationError


class NodeType(StrEnum):
    """Course tree node. Folders organize; blocks are the sequential units."""

    FOLDER = "folder"
    BLOCK = "block"


def parse_node_type(value: object) -> NodeType:
    if value is None or value == "":
        raise ValidationError("Node type is required.", code="invalid_node_type")
    try:
        return NodeType(str(value))
    except ValueError as exc:
        raise ValidationError("Unknown node type.", code="invalid_node_type") from exc


def parse_parent_id(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("Parent id must be a string or null.", code="invalid_parent")
    parent = value.strip()
    return parent or None
