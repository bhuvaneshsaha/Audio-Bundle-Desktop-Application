from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath
from uuid import UUID

from audio_bundle.shared.constants import MAX_FILENAME_LENGTH, MAX_NAME_LENGTH
from audio_bundle.shared.errors import ValidationError
from audio_bundle.shared.utilities import ensure_utc

FORBIDDEN_SECRET_KEYS = frozenset(
    {
        "password",
        "passwords",
        "main_password",
        "block_password",
        "secret",
        "secrets",
        "key",
        "keys",
        "private_key",
        "plaintext_password",
    }
)


def require_non_empty_name(value: str, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string.", code="invalid_name")
    name = value.strip()
    if not name:
        raise ValidationError(f"{field} is required.", code="empty_name")
    if len(name) > MAX_NAME_LENGTH:
        raise ValidationError(
            f"{field} must be at most {MAX_NAME_LENGTH} characters.",
            code="name_too_long",
        )
    if any(ord(ch) < 32 for ch in name):
        raise ValidationError(f"{field} contains invalid characters.", code="invalid_name")
    return name


def require_relative_source_path(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Source path is required.", code="invalid_path")
    raw = value.strip().replace("\\", "/")
    if raw.startswith("/") or raw.startswith("~") or (len(raw) >= 2 and raw[1] == ":"):
        raise ValidationError("Source path must be relative to the project directory.", code="absolute_path")
    path = PurePosixPath(raw)
    if ".." in path.parts or path.is_absolute():
        raise ValidationError("Source path must not contain parent-directory segments.", code="path_traversal")
    if any(part == "" for part in path.parts):
        raise ValidationError("Source path is invalid.", code="invalid_path")
    rendered = path.as_posix()
    if len(rendered) > 1024:
        raise ValidationError("Source path is too long.", code="path_too_long")
    return rendered


def suffix_for_filename(filename: str) -> str:
    if not isinstance(filename, str) or not filename.strip():
        raise ValidationError("Original filename is required.", code="invalid_filename")
    name = filename.strip()
    if len(name) > MAX_FILENAME_LENGTH:
        raise ValidationError("Original filename is too long.", code="filename_too_long")
    if "/" in name or "\\" in name or name in {".", ".."}:
        raise ValidationError("Original filename must not contain path separators.", code="invalid_filename")
    suffix = PurePosixPath(name).suffix.lower()
    if not suffix:
        raise ValidationError("Original filename must include a file extension.", code="missing_extension")
    return suffix


def parse_uuid(value: str, *, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError(f"{field} is not a valid identifier.", code="invalid_id") from exc


def parse_datetime(value: str, *, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{field} is required.", code="invalid_datetime")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError(f"{field} is not a valid timestamp.", code="invalid_datetime") from exc
    return ensure_utc(parsed)


def assert_no_secret_fields(payload: object, *, location: str = "document") -> None:
    if isinstance(payload, dict):
        for key, nested in payload.items():
            lowered = str(key).lower()
            if lowered in FORBIDDEN_SECRET_KEYS or lowered.endswith("_password"):
                raise ValidationError(
                    f"Refusing to load {location}: secret field '{key}' is not allowed.",
                    code="secret_field_forbidden",
                )
            assert_no_secret_fields(nested, location=location)
    elif isinstance(payload, list):
        for nested in payload:
            assert_no_secret_fields(nested, location=location)
