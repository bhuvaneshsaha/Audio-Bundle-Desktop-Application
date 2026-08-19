from __future__ import annotations

from audio_bundle.core.crypto.aead import Ciphertext, decrypt, encrypt
from audio_bundle.shared.constants import AES_KEY_SIZE
from audio_bundle.shared.errors import CryptoError


def wrap_key(kek: bytes, key: bytes, *, aad: bytes) -> Ciphertext:
    if not isinstance(key, (bytes, bytearray)) or len(key) != AES_KEY_SIZE:
        raise CryptoError("Content key must be 32 bytes.", code="invalid_key")
    return encrypt(kek, bytes(key), aad=aad)


def unwrap_key(
    kek: bytes,
    wrapped: Ciphertext,
    *,
    aad: bytes,
    failure: str = "wrong_password",
) -> bytes:
    key = decrypt(kek, wrapped, aad=aad, failure=failure)
    if len(key) != AES_KEY_SIZE:
        raise CryptoError("Unwrapped key has an unexpected length.", code="invalid_key")
    return key
