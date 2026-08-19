from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from audio_bundle.core.models.media_type import MediaType
from audio_bundle.core.validation.fields import (
    require_non_empty_name,
    require_relative_source_path,
    suffix_for_filename,
)
from audio_bundle.shared.errors import ValidationError
from audio_bundle.shared.utilities import new_id


@dataclass(slots=True)
class MediaItem:
    """A single audio file or PDF belonging to a block, in admin-defined order."""

    display_name: str
    original_filename: str
    relative_source_path: str
    media_type: MediaType
    order: int = 0
    id: str = field(default_factory=new_id)
    size_bytes: int | None = None
    source_sha256: str | None = None

    def __post_init__(self) -> None:
        self.display_name = require_non_empty_name(self.display_name, field="File display name")
        self.original_filename = require_non_empty_name(
            self.original_filename, field="Original filename"
        )
        suffix_for_filename(self.original_filename)
        self.relative_source_path = require_relative_source_path(self.relative_source_path)
        if isinstance(self.media_type, str):
            try:
                self.media_type = MediaType(self.media_type)
            except ValueError as exc:
                raise ValidationError("Unknown media type.", code="invalid_media_type") from exc
        inferred = MediaType.from_filename(self.original_filename)
        if self.media_type != inferred:
            raise ValidationError(
                f"Media type '{self.media_type}' does not match file '{self.original_filename}'.",
                code="media_type_mismatch",
            )
        if not isinstance(self.order, int) or self.order < 0:
            raise ValidationError("File order must be a non-negative integer.", code="invalid_order")
        if self.size_bytes is not None and (not isinstance(self.size_bytes, int) or self.size_bytes < 0):
            raise ValidationError("File size is invalid.", code="invalid_size")

    @classmethod
    def from_import(
        cls,
        *,
        original_filename: str,
        relative_source_path: str,
        display_name: str | None = None,
        order: int = 0,
        size_bytes: int | None = None,
        source_sha256: str | None = None,
    ) -> MediaItem:
        media_type = MediaType.from_filename(original_filename)
        label = display_name if display_name is not None else original_filename
        return cls(
            display_name=label,
            original_filename=original_filename,
            relative_source_path=relative_source_path,
            media_type=media_type,
            order=order,
            size_bytes=size_bytes,
            source_sha256=source_sha256,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["media_type"] = str(self.media_type)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> MediaItem:
        if not isinstance(payload, dict):
            raise ValidationError("File entry must be an object.", code="invalid_item")
        required = ("display_name", "original_filename", "relative_source_path", "media_type")
        missing = [key for key in required if key not in payload]
        if missing:
            raise ValidationError(f"File entry is missing fields: {', '.join(missing)}.", code="missing_field")
        return cls(
            id=str(payload["id"]) if "id" in payload else new_id(),
            display_name=payload["display_name"],
            original_filename=payload["original_filename"],
            relative_source_path=payload["relative_source_path"],
            media_type=payload["media_type"],
            order=int(payload.get("order", 0)),
            size_bytes=payload.get("size_bytes"),
            source_sha256=payload.get("source_sha256"),
        )
