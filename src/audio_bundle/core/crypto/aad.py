from __future__ import annotations

from audio_bundle.shared.constants import BUNDLE_FORMAT_VERSION, BUNDLE_MAGIC
from audio_bundle.shared.errors import CryptoError

_CHUNK_TYPES = frozenset({b"WKEY", b"BWKY", b"EMAN", b"BMAN", b"BLOB"})


def bind_aad(
    chunk_type: bytes,
    *,
    context: bytes = b"",
    format_version: int = BUNDLE_FORMAT_VERSION,
) -> bytes:
    """Bind ciphertext to format version, chunk role, and optional context (ids)."""
    if chunk_type not in _CHUNK_TYPES:
        raise CryptoError("Unknown AEAD chunk type.", code="invalid_aad")
    if not isinstance(context, (bytes, bytearray)):
        raise CryptoError("AAD context must be bytes.", code="invalid_aad")
    if format_version < 1 or format_version > 65535:
        raise CryptoError("Invalid format version for AAD.", code="invalid_aad")
    return (
        BUNDLE_MAGIC
        + int(format_version).to_bytes(2, "little")
        + chunk_type
        + bytes(context)
    )
