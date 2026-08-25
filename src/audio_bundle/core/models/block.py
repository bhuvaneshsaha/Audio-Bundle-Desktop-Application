from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from audio_bundle.core.models.auth_method import (
    BlockAuthMethod,
    parse_block_auth_method,
    parse_windows_principals,
)
from audio_bundle.core.models.media_item import MediaItem
from audio_bundle.core.validation.fields import require_non_empty_name
from audio_bundle.core.validation.project import validate_block_graph
from audio_bundle.shared.errors import ValidationError
from audio_bundle.shared.utilities import new_id


def _renumber(items: list[MediaItem]) -> None:
    for index, item in enumerate(items):
        item.order = index


@dataclass(slots=True)
class Block:
    """A named group of ordered files. Passwords are never stored on this model."""

    name: str
    order: int = 0
    id: str = field(default_factory=new_id)
    folder_id: str | None = None
    items: list[MediaItem] = field(default_factory=list)
    auth_method: BlockAuthMethod = BlockAuthMethod.PASSWORD
    windows_principals: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.name = require_non_empty_name(self.name, field="Block name")
        if not isinstance(self.order, int) or self.order < 0:
            raise ValidationError("Block order must be a non-negative integer.", code="invalid_order")
        if not isinstance(self.items, list):
            raise ValidationError("Block files must be a list.", code="invalid_items")
        if isinstance(self.auth_method, str):
            self.auth_method = parse_block_auth_method(self.auth_method)
        self.windows_principals = parse_windows_principals(self.windows_principals)
        if self.folder_id is not None:
            self.folder_id = str(self.folder_id).strip() or None
        _renumber(self.items)
        validate_block_graph(self)

    def add_item(self, item: MediaItem, *, index: int | None = None) -> MediaItem:
        if index is None:
            self.items.append(item)
        else:
            if index < 0 or index > len(self.items):
                raise ValidationError("Invalid insert index.", code="invalid_index")
            self.items.insert(index, item)
        _renumber(self.items)
        validate_block_graph(self)
        return item

    def remove_item(self, item_id: str) -> MediaItem:
        for index, item in enumerate(self.items):
            if item.id == item_id:
                removed = self.items.pop(index)
                _renumber(self.items)
                return removed
        raise ValidationError("File not found in this block.", code="item_not_found")

    def move_item(self, from_index: int, to_index: int) -> None:
        if from_index < 0 or from_index >= len(self.items):
            raise ValidationError("Invalid source index.", code="invalid_index")
        if to_index < 0 or to_index >= len(self.items):
            raise ValidationError("Invalid destination index.", code="invalid_index")
        item = self.items.pop(from_index)
        self.items.insert(to_index, item)
        _renumber(self.items)

    def rename_item(self, item_id: str, display_name: str) -> MediaItem:
        for item in self.items:
            if item.id == item_id:
                item.display_name = require_non_empty_name(display_name, field="File display name")
                return item
        raise ValidationError("File not found in this block.", code="item_not_found")

    def ordered_audio_items(self) -> list[MediaItem]:
        return [item for item in self.items if item.media_type.is_playable_audio()]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "order": self.order,
            "folder_id": self.folder_id,
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Block:
        if not isinstance(payload, dict):
            raise ValidationError("Block must be an object.", code="invalid_block")
        if "name" not in payload:
            raise ValidationError("Block name is required.", code="missing_field")
        raw_items = payload.get("items", [])
        if not isinstance(raw_items, list):
            raise ValidationError("Block files must be a list.", code="invalid_items")
        items = [MediaItem.from_dict(raw) for raw in raw_items]
        items.sort(key=lambda item: item.order)
        return cls(
            id=str(payload["id"]) if "id" in payload else new_id(),
            name=payload["name"],
            order=int(payload.get("order", 0)),
            folder_id=str(payload["folder_id"]) if payload.get("folder_id") else None,
            items=items,
            auth_method=parse_block_auth_method(payload.get("auth_method")),
            windows_principals=parse_windows_principals(payload.get("windows_principals")),
        )
