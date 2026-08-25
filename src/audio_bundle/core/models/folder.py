from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from audio_bundle.core.validation.fields import require_non_empty_name
from audio_bundle.shared.errors import ValidationError
from audio_bundle.shared.utilities import new_id


@dataclass(slots=True)
class ProjectFolder:
    """Logical folder used to organize blocks in the admin project."""

    name: str
    order: int = 0
    parent_id: str | None = None
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        self.name = require_non_empty_name(self.name, field="Folder name")
        if self.parent_id is not None:
            parent = str(self.parent_id).strip()
            self.parent_id = parent or None
        if not isinstance(self.order, int) or self.order < 0:
            raise ValidationError("Folder order must be a non-negative integer.", code="invalid_order")

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "name": self.name,
            "order": self.order,
        }
        if self.parent_id:
            payload["parent_id"] = self.parent_id
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ProjectFolder:
        if not isinstance(payload, dict):
            raise ValidationError("Folder must be an object.", code="invalid_folder")
        if "name" not in payload:
            raise ValidationError("Folder name is required.", code="missing_field")
        return cls(
            id=str(payload["id"]) if "id" in payload else new_id(),
            name=payload["name"],
            order=int(payload.get("order", 0)),
            parent_id=str(payload["parent_id"]) if "parent_id" in payload else None,
        )
