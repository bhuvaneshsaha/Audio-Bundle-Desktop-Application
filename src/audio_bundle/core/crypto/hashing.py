from __future__ import annotations

import hashlib
import hmac

from audio_bundle.shared.errors import AuthenticationError, CryptoError


def sha256_digest(data: bytes) -> bytes:
    if not isinstance(data, (bytes, bytearray)):
        raise CryptoError("Hash input must be bytes.", code="invalid_hash_input")
    return hashlib.sha256(bytes(data)).digest()


def sha256_hex(data: bytes) -> str:
    return sha256_digest(data).hex()


def verify_sha256(data: bytes, expected_hex: str) -> None:
    if not isinstance(expected_hex, str) or len(expected_hex) != 64:
        raise AuthenticationError("Integrity hash is missing or invalid.", code="invalid_content_hash")
    try:
        expected = bytes.fromhex(expected_hex)
    except ValueError as exc:
        raise AuthenticationError("Integrity hash is missing or invalid.", code="invalid_content_hash") from exc
    actual = sha256_digest(data)
    if not hmac.compare_digest(actual, expected):
        raise AuthenticationError(
            "Decrypted content failed its integrity check.",
            code="content_hash_mismatch",
        )
