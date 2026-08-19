from __future__ import annotations

from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from audio_bundle.core.crypto.random import random_nonce
from audio_bundle.shared.constants import AES_KEY_SIZE, GCM_NONCE_SIZE, GCM_TAG_SIZE
from audio_bundle.shared.errors import AuthenticationError, CryptoError

_WRONG_PASSWORD_MESSAGE = "The password is incorrect or the data is not valid."
_TAMPER_MESSAGE = "The bundle is corrupted or has been modified."


@dataclass(frozen=True, slots=True)
class Ciphertext:
    nonce: bytes
    ciphertext: bytes  # AES-GCM output: ciphertext || tag

    def __post_init__(self) -> None:
        if len(self.nonce) != GCM_NONCE_SIZE:
            raise CryptoError("GCM nonce must be 12 bytes.", code="invalid_nonce")
        if len(self.ciphertext) < GCM_TAG_SIZE:
            raise CryptoError("Ciphertext is too short to contain an authentication tag.", code="invalid_ciphertext")

    def to_bytes(self) -> bytes:
        return self.nonce + self.ciphertext

    @classmethod
    def from_bytes(cls, payload: bytes) -> Ciphertext:
        if len(payload) < GCM_NONCE_SIZE + GCM_TAG_SIZE:
            raise CryptoError("Encrypted payload is truncated.", code="truncated_ciphertext")
        return cls(nonce=payload[:GCM_NONCE_SIZE], ciphertext=payload[GCM_NONCE_SIZE:])


def _aesgcm(key: bytes) -> AESGCM:
    if not isinstance(key, (bytes, bytearray)) or len(key) != AES_KEY_SIZE:
        raise CryptoError("AES-256-GCM key must be 32 bytes.", code="invalid_key")
    return AESGCM(bytes(key))


def encrypt(key: bytes, plaintext: bytes, *, aad: bytes) -> Ciphertext:
    if not isinstance(plaintext, (bytes, bytearray)):
        raise CryptoError("Plaintext must be bytes.", code="invalid_plaintext")
    if not isinstance(aad, (bytes, bytearray)):
        raise CryptoError("AAD must be bytes.", code="invalid_aad")
    nonce = random_nonce()
    ciphertext = _aesgcm(key).encrypt(nonce, bytes(plaintext), bytes(aad))
    return Ciphertext(nonce=nonce, ciphertext=ciphertext)


def decrypt(
    key: bytes,
    blob: Ciphertext,
    *,
    aad: bytes,
    failure: str = "tampered",
) -> bytes:
    if not isinstance(aad, (bytes, bytearray)):
        raise CryptoError("AAD must be bytes.", code="invalid_aad")
    if failure == "wrong_password":
        message, code = _WRONG_PASSWORD_MESSAGE, "wrong_password"
    elif failure == "tampered":
        message, code = _TAMPER_MESSAGE, "tampered"
    else:
        raise CryptoError("Unknown authentication failure mode.", code="invalid_failure_mode")
    try:
        return _aesgcm(key).decrypt(blob.nonce, blob.ciphertext, bytes(aad))
    except InvalidTag as exc:
        raise AuthenticationError(message, code=code) from exc
