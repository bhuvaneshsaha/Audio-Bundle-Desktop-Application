from __future__ import annotations

from enum import StrEnum

from audio_bundle.shared.errors import ValidationError


class BlockAuthMethod(StrEnum):
    """How a Client user proves they may open a block."""

    PASSWORD = "password"
    WINDOWS = "windows"
    NONE = "none"


def parse_block_auth_method(value: object) -> BlockAuthMethod:
    if value is None or value == "":
        return BlockAuthMethod.PASSWORD
    try:
        return BlockAuthMethod(str(value))
    except ValueError as exc:
        raise ValidationError("Unknown block authentication method.", code="invalid_auth_method") from exc


def parse_windows_principals(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = [value]
    elif isinstance(value, list):
        raw = value
    else:
        raise ValidationError("Windows allow-list must be a list of names.", code="invalid_windows_principals")
    principals: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            raise ValidationError("Windows allow-list entries must be strings.", code="invalid_windows_principals")
        name = item.strip()
        if name:
            principals.append(name)
    return principals
