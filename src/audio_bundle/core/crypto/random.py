from __future__ import annotations

import secrets

from audio_bundle.shared.constants import AES_KEY_SIZE, GCM_NONCE_SIZE, KDF_SALT_SIZE
from audio_bundle.shared.errors import CryptoError


def random_bytes(size: int) -> bytes:
    if size < 1:
        raise CryptoError("Refusing to generate an empty random buffer.", code="invalid_random_size")
    return secrets.token_bytes(size)


def random_key() -> bytes:
    return random_bytes(AES_KEY_SIZE)


def random_nonce() -> bytes:
    return random_bytes(GCM_NONCE_SIZE)


def random_salt() -> bytes:
    return random_bytes(KDF_SALT_SIZE)
