from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from audio_bundle.core.models.auth_method import (
    BlockAuthMethod,
    parse_block_auth_method,
    parse_windows_principals,
)
from audio_bundle.core.models.media_type import MediaType
from audio_bundle.core.validation.fields import parse_datetime, require_non_empty_name
from audio_bundle.shared.constants import BUNDLE_FORMAT_VERSION
from audio_bundle.shared.errors import ValidationError
from audio_bundle.shared.utilities import isoformat_utc, new_id, utc_now


def _renumber_files(files: list[BundleFileEntry]) -> None:
    for index, entry in enumerate(files):
        entry.order = index


def _renumber_blocks(blocks: list[BundleBlockSummary]) -> None:
    for index, block in enumerate(blocks):
        block.order = index


@dataclass(slots=True)
class BundleFileEntry:
    """File metadata stored in the inner (block-password) manifest."""

    display_name: str
    original_filename: str
    media_type: MediaType
    order: int = 0
    id: str = field(default_factory=new_id)
    size_bytes: int = 0
    plaintext_sha256: str | None = None
    blob_id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        self.display_name = require_non_empty_name(self.display_name, field="File display name")
        self.original_filename = require_non_empty_name(
            self.original_filename, field="Original filename"
        )
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
        if not isinstance(self.size_bytes, int) or self.size_bytes < 0:
            raise ValidationError("File size is invalid.", code="invalid_size")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "blob_id": self.blob_id,
            "display_name": self.display_name,
            "original_filename": self.original_filename,
            "media_type": str(self.media_type),
            "order": self.order,
            "size_bytes": self.size_bytes,
            "plaintext_sha256": self.plaintext_sha256,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> BundleFileEntry:
        if not isinstance(payload, dict):
            raise ValidationError("Bundle file entry must be an object.", code="invalid_item")
        return cls(
            id=str(payload["id"]) if "id" in payload else new_id(),
            blob_id=str(payload["blob_id"]) if "blob_id" in payload else new_id(),
            display_name=payload["display_name"],
            original_filename=payload["original_filename"],
            media_type=payload["media_type"],
            order=int(payload.get("order", 0)),
            size_bytes=int(payload.get("size_bytes", 0)),
            plaintext_sha256=payload.get("plaintext_sha256"),
        )


@dataclass(slots=True)
class BundleBlockSummary:
    """Block identity visible after the main password. No file list."""

    name: str
    order: int = 0
    id: str = field(default_factory=new_id)
    folder_path: list[str] = field(default_factory=list)
    auth_method: BlockAuthMethod = BlockAuthMethod.PASSWORD
    windows_principals: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.name = require_non_empty_name(self.name, field="Block name")
        if not isinstance(self.order, int) or self.order < 0:
            raise ValidationError("Block order must be a non-negative integer.", code="invalid_order")
        if isinstance(self.auth_method, str):
            self.auth_method = parse_block_auth_method(self.auth_method)
        if not isinstance(self.folder_path, list):
            raise ValidationError("Folder path must be a list.", code="invalid_folder_path")
        self.folder_path = [require_non_empty_name(str(part), field="Folder name") for part in self.folder_path]
        self.windows_principals = parse_windows_principals(self.windows_principals)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "name": self.name,
            "order": self.order,
            "folder_path": list(self.folder_path),
            "auth_method": str(self.auth_method),
        }
        if self.auth_method is BlockAuthMethod.WINDOWS:
            payload["windows_principals"] = list(self.windows_principals)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> BundleBlockSummary:
        if not isinstance(payload, dict):
            raise ValidationError("Bundle block summary must be an object.", code="invalid_block")
        return cls(
            id=str(payload["id"]) if "id" in payload else new_id(),
            name=payload["name"],
            order=int(payload.get("order", 0)),
            folder_path=[str(part) for part in payload.get("folder_path", [])],
            auth_method=parse_block_auth_method(payload.get("auth_method")),
            windows_principals=parse_windows_principals(payload.get("windows_principals")),
        )


@dataclass(slots=True)
class BundleBlockContents:
    """Inner manifest: file list and order, encrypted under the block key."""

    block_id: str
    name: str
    files: list[BundleFileEntry] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.name = require_non_empty_name(self.name, field="Block name")
        self.files = sorted(self.files, key=lambda entry: entry.order)
        _renumber_files(self.files)
        ids = [entry.id for entry in self.files]
        if len(ids) != len(set(ids)):
            raise ValidationError("Duplicate file id in block contents.", code="duplicate_id")

    def ordered_audio_files(self) -> list[BundleFileEntry]:
        return [entry for entry in self.files if entry.media_type.is_playable_audio()]

    def to_dict(self) -> dict[str, Any]:
        return {
            "block_id": self.block_id,
            "name": self.name,
            "files": [entry.to_dict() for entry in self.files],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> BundleBlockContents:
        if not isinstance(payload, dict):
            raise ValidationError("Block contents must be an object.", code="invalid_block")
        raw_files = payload.get("files", [])
        if not isinstance(raw_files, list):
            raise ValidationError("Block files must be a list.", code="invalid_items")
        files = [BundleFileEntry.from_dict(raw) for raw in raw_files]
        return cls(block_id=str(payload["block_id"]), name=payload["name"], files=files)

    @classmethod
    def from_block(cls, block: Any) -> BundleBlockContents:
        from audio_bundle.core.models.block import Block

        if not isinstance(block, Block):
            raise ValidationError("Expected a Block model.", code="invalid_block")
        files = [
            BundleFileEntry(
                id=item.id,
                display_name=item.display_name,
                original_filename=item.original_filename,
                media_type=item.media_type,
                order=item.order,
                size_bytes=item.size_bytes or 0,
                plaintext_sha256=item.source_sha256,
            )
            for item in block.items
        ]
        return cls(block_id=block.id, name=block.name, files=files)


@dataclass(slots=True)
class BundleManifest:
    """Outer manifest: course metadata and block list, encrypted under the bundle key."""

    title: str
    format_version: int = BUNDLE_FORMAT_VERSION
    bundle_id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utc_now)
    blocks: list[BundleBlockSummary] = field(default_factory=list)
    autoplay_on_open: bool = False
    single_active_block: bool = False
    sequential_unlock: bool = False
    block_auth_method: BlockAuthMethod = BlockAuthMethod.PASSWORD
    windows_principals: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.title = require_non_empty_name(self.title, field="Bundle title")
        if self.format_version != BUNDLE_FORMAT_VERSION:
            raise ValidationError(
                f"Unsupported bundle format version {self.format_version}.",
                code="unsupported_bundle_version",
            )
        self.blocks = sorted(self.blocks, key=lambda block: block.order)
        _renumber_blocks(self.blocks)
        ids = [block.id for block in self.blocks]
        if len(ids) != len(set(ids)):
            raise ValidationError("Duplicate block id in bundle manifest.", code="duplicate_id")
        if isinstance(self.block_auth_method, str):
            self.block_auth_method = parse_block_auth_method(self.block_auth_method)
        self.windows_principals = parse_windows_principals(self.windows_principals)
        for block in self.blocks:
            block.auth_method = self.block_auth_method
            block.windows_principals = list(self.windows_principals)

    def to_dict(self) -> dict[str, Any]:
        return {
            "format_version": self.format_version,
            "bundle_id": self.bundle_id,
            "title": self.title,
            "created_at": isoformat_utc(self.created_at),
            "autoplay_on_open": self.autoplay_on_open,
            "single_active_block": self.single_active_block,
            "sequential_unlock": self.sequential_unlock,
            "block_auth_method": str(self.block_auth_method),
            "windows_principals": list(self.windows_principals),
            "blocks": [block.to_dict() for block in self.blocks],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> BundleManifest:
        if not isinstance(payload, dict):
            raise ValidationError("Bundle manifest must be an object.", code="invalid_manifest")
        if "title" not in payload:
            raise ValidationError("Bundle title is required.", code="missing_field")
        raw_blocks = payload.get("blocks", [])
        if not isinstance(raw_blocks, list):
            raise ValidationError("Bundle blocks must be a list.", code="invalid_blocks")
        blocks = [BundleBlockSummary.from_dict(raw) for raw in raw_blocks]
        auth_method = payload.get("block_auth_method")
        if auth_method is None and blocks:
            auth_method = blocks[0].auth_method
        principals = payload.get("windows_principals")
        if principals is None and blocks:
            principals = blocks[0].windows_principals
        created_at = payload.get("created_at")
        return cls(
            title=payload["title"],
            format_version=int(payload.get("format_version", BUNDLE_FORMAT_VERSION)),
            bundle_id=str(payload["bundle_id"]) if "bundle_id" in payload else new_id(),
            created_at=(
                created_at
                if isinstance(created_at, datetime)
                else parse_datetime(created_at, field="created_at")
                if created_at
                else utc_now()
            ),
            blocks=blocks,
            autoplay_on_open=bool(payload.get("autoplay_on_open", False)),
            single_active_block=bool(payload.get("single_active_block", False)),
            sequential_unlock=bool(payload.get("sequential_unlock", False)),
            block_auth_method=parse_block_auth_method(auth_method),
            windows_principals=parse_windows_principals(principals),
        )

    @classmethod
    def from_project(cls, project: Any) -> BundleManifest:
        from audio_bundle.core.models.project import Project

        if not isinstance(project, Project):
            raise ValidationError("Expected a Project model.", code="invalid_project")
        method = getattr(project, "block_auth_method", BlockAuthMethod.PASSWORD)
        principals = list(getattr(project, "windows_principals", []))
        children: dict[str | None, list[object]] = {}
        for folder in project.folders:
            children.setdefault(folder.parent_id, []).append(folder)
        for group in children.values():
            group.sort(key=lambda folder: folder.order)
        ordered_folders: list[str] = []

        def walk(parent_id: str | None) -> None:
            for folder in children.get(parent_id, []):
                ordered_folders.append(folder.id)
                walk(folder.id)

        walk(None)
        folder_blocks: dict[str, list[object]] = {folder_id: [] for folder_id in ordered_folders}
        for block in project.blocks:
            if block.folder_id is None:
                continue
            folder_blocks.setdefault(block.folder_id, []).append(block)
        ordered_blocks: list[object] = []
        for folder_id in ordered_folders:
            ordered_blocks.extend(sorted(folder_blocks.get(folder_id, []), key=lambda block: block.order))
        return cls(
            title=project.name,
            autoplay_on_open=bool(getattr(project, "autoplay_on_open", False)),
            single_active_block=bool(getattr(project, "single_active_block", False)),
            sequential_unlock=bool(getattr(project, "sequential_unlock", False)),
            block_auth_method=method,
            windows_principals=principals,
            blocks=[
                BundleBlockSummary(
                    id=block.id,
                    name=block.name,
                    order=index,
                    folder_path=project.folder_path(block.folder_id),
                    auth_method=method,
                    windows_principals=principals,
                )
                for index, block in enumerate(ordered_blocks)
            ],
        )
