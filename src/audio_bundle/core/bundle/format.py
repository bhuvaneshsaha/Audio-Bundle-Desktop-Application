from __future__ import annotations

import json
import struct
import zlib
from dataclasses import dataclass

from audio_bundle.shared.constants import (
    BUNDLE_FOOTER_MAGIC,
    BUNDLE_FORMAT_VERSION,
    BUNDLE_MAGIC,
)
from audio_bundle.shared.errors import BundleError

HEADER_SIZE = 24
CHUNK_HEADER_SIZE = 10
FOOTER_SIZE = 16
CHUNK_FLAG_CRITICAL = 0x0001

CHUNK_KDFP = b"KDFP"
CHUNK_WKEY = b"WKEY"
CHUNK_EMAN = b"EMAN"
CHUNK_BKDF = b"BKDF"
CHUNK_BWKY = b"BWKY"
CHUNK_BMAN = b"BMAN"
CHUNK_BLOB = b"BLOB"
CHUNK_FEND = b"FEND"

KNOWN_CHUNKS = frozenset(
    {
        CHUNK_KDFP,
        CHUNK_WKEY,
        CHUNK_EMAN,
        CHUNK_BKDF,
        CHUNK_BWKY,
        CHUNK_BMAN,
        CHUNK_BLOB,
        CHUNK_FEND,
    }
)

_HEADER = struct.Struct("<16sHHI")
_CHUNK = struct.Struct("<4sHI")
_FOOTER = struct.Struct("<8sQ")

AAD_MAIN_WRAP_CONTEXT = b"main-wrap"
AAD_OUTER_MANIFEST_CONTEXT = b"outer-manifest"

MAX_CHUNKS = 20_000


@dataclass(frozen=True, slots=True)
class Chunk:
    type: bytes
    flags: int
    payload: bytes


def encode_json(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def decode_json(raw: bytes) -> dict[str, object]:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleError("Encrypted manifest is not valid JSON.", code="invalid_manifest") from exc
    if not isinstance(data, dict):
        raise BundleError("Encrypted manifest is not valid JSON.", code="invalid_manifest")
    return data


def build_header(*, format_version: int = BUNDLE_FORMAT_VERSION, flags: int = 0) -> bytes:
    prefix = BUNDLE_MAGIC + struct.pack("<HH", format_version, flags)
    crc = zlib.crc32(prefix) & 0xFFFFFFFF
    return prefix + struct.pack("<I", crc)


def encode_chunk(chunk_type: bytes, payload: bytes, *, flags: int = CHUNK_FLAG_CRITICAL) -> bytes:
    if chunk_type not in KNOWN_CHUNKS:
        raise BundleError("Refusing to write an unknown chunk type.", code="invalid_chunk")
    if len(payload) > 0xFFFFFFFF:
        raise BundleError("Chunk payload is too large.", code="chunk_too_large")
    return _CHUNK.pack(chunk_type, flags, len(payload)) + payload


def build_footer(total_size: int) -> bytes:
    return _FOOTER.pack(BUNDLE_FOOTER_MAGIC, total_size)


def _looks_like_zip(data: bytes) -> bool:
    return data.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"))


def parse_container(data: bytes) -> tuple[int, list[Chunk]]:
    if not data:
        raise BundleError("The file is empty.", code="truncated_bundle")
    if _looks_like_zip(data):
        raise BundleError(
            "This file is a ZIP archive, not an Audio Bundle. ZIP passwords are not supported.",
            code="zip_not_supported",
        )
    if len(data) < HEADER_SIZE + FOOTER_SIZE:
        raise BundleError("The bundle is truncated.", code="truncated_bundle")

    footer_magic, declared_size = _FOOTER.unpack(data[-FOOTER_SIZE:])
    if footer_magic != BUNDLE_FOOTER_MAGIC:
        raise BundleError("The bundle footer is missing or invalid.", code="truncated_bundle")
    if declared_size != len(data):
        raise BundleError("The bundle is truncated or has extra trailing data.", code="truncated_bundle")

    magic, version, flags, crc = _HEADER.unpack(data[:HEADER_SIZE])
    if magic != BUNDLE_MAGIC:
        raise BundleError("This file is not a valid Audio Bundle.", code="invalid_magic")
    expected_crc = zlib.crc32(data[:20]) & 0xFFFFFFFF
    if crc != expected_crc:
        raise BundleError("The bundle header is corrupted.", code="header_checksum_mismatch")
    if version != BUNDLE_FORMAT_VERSION:
        raise BundleError(
            f"Unsupported bundle format version {version}.",
            code="unsupported_bundle_version",
        )
    _ = flags

    chunks: list[Chunk] = []
    offset = HEADER_SIZE
    end = len(data) - FOOTER_SIZE
    while offset < end:
        if len(chunks) >= MAX_CHUNKS:
            raise BundleError("The bundle contains too many chunks.", code="invalid_chunk_sequence")
        if offset + CHUNK_HEADER_SIZE > end:
            raise BundleError("The bundle is truncated.", code="truncated_bundle")
        chunk_type, chunk_flags, payload_len = _CHUNK.unpack(data[offset : offset + CHUNK_HEADER_SIZE])
        offset += CHUNK_HEADER_SIZE
        if offset + payload_len > end:
            raise BundleError("The bundle is truncated.", code="truncated_bundle")
        payload = data[offset : offset + payload_len]
        offset += payload_len
        if chunk_type not in KNOWN_CHUNKS:
            if chunk_flags & CHUNK_FLAG_CRITICAL:
                raise BundleError("The bundle contains an unsupported critical chunk.", code="unknown_chunk")
            continue
        chunks.append(Chunk(type=chunk_type, flags=chunk_flags, payload=payload))

    if offset != end:
        raise BundleError("The bundle chunk table is invalid.", code="invalid_chunk_sequence")
    return version, chunks
