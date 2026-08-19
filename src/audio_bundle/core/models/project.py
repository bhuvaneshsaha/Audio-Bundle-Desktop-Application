from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from audio_bundle.core.models.block import Block
from audio_bundle.core.validation.fields import parse_datetime, require_non_empty_name
from audio_bundle.core.validation.project import validate_project_graph
from audio_bundle.shared.constants import PROJECT_SCHEMA_VERSION
from audio_bundle.shared.errors import ValidationError
from audio_bundle.shared.utilities import isoformat_utc, new_id, utc_now


def _renumber(blocks: list[Block]) -> None:
    for index, block in enumerate(blocks):
        block.order = index


@dataclass(slots=True)
class Project:
    """Editable admin project. Distinct from a generated .audiobundle file."""

    name: str
    id: str = field(default_factory=new_id)
    schema_version: int = PROJECT_SCHEMA_VERSION
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    blocks: list[Block] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.name = require_non_empty_name(self.name, field="Project name")
        if self.schema_version != PROJECT_SCHEMA_VERSION:
            raise ValidationError(
                f"Unsupported project schema version {self.schema_version}.",
                code="unsupported_schema_version",
            )
        _renumber(self.blocks)
        validate_project_graph(self)

    def touch(self) -> None:
        self.updated_at = utc_now()

    def add_block(self, block: Block, *, index: int | None = None) -> Block:
        if index is None:
            self.blocks.append(block)
        else:
            if index < 0 or index > len(self.blocks):
                raise ValidationError("Invalid insert index.", code="invalid_index")
            self.blocks.insert(index, block)
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
        blocks = [Block.from_dict(raw) for raw in raw_blocks]
        blocks.sort(key=lambda block: block.order)
        created_at = payload.get("created_at")
        updated_at = payload.get("updated_at")
        return cls(
            id=str(payload["id"]) if "id" in payload else new_id(),
            name=payload["name"],
            schema_version=int(payload.get("schema_version", PROJECT_SCHEMA_VERSION)),
            created_at=parse_datetime(created_at, field="created_at") if created_at else utc_now(),
            updated_at=parse_datetime(updated_at, field="updated_at") if updated_at else utc_now(),
            blocks=blocks,
        )
