from __future__ import annotations

from dataclasses import dataclass

from audio_bundle.core.bundle.format import (
    CHUNK_BKDF,
    CHUNK_BMAN,
    CHUNK_BLOB,
    CHUNK_BWKY,
    CHUNK_EMAN,
    CHUNK_FEND,
    CHUNK_KDFP,
    CHUNK_WKEY,
    Chunk,
)
from audio_bundle.shared.errors import BundleError


@dataclass(frozen=True, slots=True)
class BlockRegion:
    kdf: bytes
    wrapped_key: bytes
    encrypted_manifest: bytes
    encrypted_blobs: list[bytes]


@dataclass(frozen=True, slots=True)
class ParsedBundle:
    main_kdf: bytes
    wrapped_bundle_key: bytes
    encrypted_manifest: bytes
    blocks: list[BlockRegion]


def group_chunks(chunks: list[Chunk]) -> ParsedBundle:
    if not chunks or chunks[-1].type != CHUNK_FEND:
        raise BundleError("The bundle is missing its end marker.", code="invalid_chunk_sequence")
    if any(chunk.type == CHUNK_FEND for chunk in chunks[:-1]):
        raise BundleError("The bundle end marker appears more than once.", code="invalid_chunk_sequence")

    body = chunks[:-1]
    if len(body) < 3:
        raise BundleError("The bundle is missing required cryptographic chunks.", code="invalid_chunk_sequence")
    if body[0].type != CHUNK_KDFP or body[1].type != CHUNK_WKEY or body[2].type != CHUNK_EMAN:
        raise BundleError("The bundle chunk order is invalid.", code="invalid_chunk_sequence")

    blocks: list[BlockRegion] = []
    index = 3
    while index < len(body):
        if body[index].type != CHUNK_BKDF:
            raise BundleError("The bundle chunk order is invalid.", code="invalid_chunk_sequence")
        if index + 2 >= len(body) or body[index + 1].type != CHUNK_BWKY or body[index + 2].type != CHUNK_BMAN:
            raise BundleError("The bundle is missing block metadata.", code="invalid_chunk_sequence")
        kdf = body[index].payload
        wrapped_key = body[index + 1].payload
        encrypted_manifest = body[index + 2].payload
        index += 3
        blobs: list[bytes] = []
        while index < len(body) and body[index].type == CHUNK_BLOB:
            blobs.append(body[index].payload)
            index += 1
        blocks.append(
            BlockRegion(
                kdf=kdf,
                wrapped_key=wrapped_key,
                encrypted_manifest=encrypted_manifest,
                encrypted_blobs=blobs,
            )
        )
    return ParsedBundle(
        main_kdf=body[0].payload,
        wrapped_bundle_key=body[1].payload,
        encrypted_manifest=body[2].payload,
        blocks=blocks,
    )
