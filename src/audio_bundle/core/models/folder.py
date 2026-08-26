from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from audio_bundle.core.models.node import NodeType, parse_parent_id
from audio_bundle.core.validation.fields import require_non_empty_name
from audio_bundle.shared.errors import ValidationError
from audio_bundle.shared.utilities import new_id


@dataclass(slots=True)
class Folder:
    """Organizational node. Names are labels only and never affect sequencing."""

    name: str
    id: str = field(default_factory=new_id)
    parent_id: str | None = None
    order: int = 0

    @property
    def node_type(self) -> NodeType:
        return NodeType.FOLDER

    def __post_init__(self) -> None:
        self.name = require_non_empty_name(self.name, field="Folder name")
        self.parent_id = parse_parent_id(self.parent_id)
        if not isinstance(self.order, int) or self.order < 0:
            raise ValidationError("Folder order must be a non-negative integer.", code="invalid_order")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "name": self.name,
            "node_type": str(NodeType.FOLDER),
            "sort_order": self.order,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Folder:
        if not isinstance(payload, dict):
            raise ValidationError("Folder must be an object.", code="invalid_folder")
        if "name" not in payload:
            raise ValidationError("Folder name is required.", code="missing_field")
        order = payload.get("sort_order", payload.get("order", 0))
        return cls(
            id=str(payload["id"]) if "id" in payload else new_id(),
            parent_id=parse_parent_id(payload.get("parent_id")),
            name=payload["name"],
            order=int(order),
        )
