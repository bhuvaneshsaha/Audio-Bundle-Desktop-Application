from __future__ import annotations

from dataclasses import dataclass

from audio_bundle.core.crypto.aead import Ciphertext
from audio_bundle.core.crypto.envelope import unwrap_key, wrap_key
from audio_bundle.core.crypto.kdf import KdfParams, KdfProfile, derive_key
from audio_bundle.core.crypto.random import random_key
from audio_bundle.shared.errors import CryptoError

_SEAL_MAGIC = b"ABSEAL01"


@dataclass(frozen=True, slots=True)
class SealedKey:
    """Random content key wrapped by a password-derived KEK."""

    params: KdfParams
    wrapped: Ciphertext

    def to_bytes(self) -> bytes:
        record = self.params.to_bytes()
        blob = self.wrapped.to_bytes()
        return (
            _SEAL_MAGIC
            + len(record).to_bytes(2, "little")
            + record
            + blob
        )

    @classmethod
    def from_bytes(cls, payload: bytes) -> SealedKey:
        if len(payload) < 10 or payload[:8] != _SEAL_MAGIC:
            raise CryptoError("Sealed key record is invalid.", code="invalid_sealed_key")
        record_len = int.from_bytes(payload[8:10], "little")
        start = 10
        end = start + record_len
        if end > len(payload):
            raise CryptoError("Sealed key record is truncated.", code="invalid_sealed_key")
        params = KdfParams.from_bytes(payload[start:end])
        wrapped = Ciphertext.from_bytes(payload[end:])
        return cls(params=params, wrapped=wrapped)


class CryptoEngine:
    """Envelope-encryption helpers used by the bundle writer/reader."""

    def __init__(self, *, kdf_profile: KdfProfile = KdfProfile.PRODUCTION) -> None:
        self.kdf_profile = KdfProfile(kdf_profile)

    def new_content_key(self) -> bytes:
        return random_key()

    def seal_key(self, password: str, key: bytes, *, aad: bytes) -> SealedKey:
        params = KdfParams.generate(profile=self.kdf_profile)
        kek = derive_key(password, params)
        wrapped = wrap_key(kek, key, aad=aad)
        return SealedKey(params=params, wrapped=wrapped)

    def wrap_with_key(self, kek: bytes, key: bytes, *, aad: bytes) -> SealedKey:
        wrapped = wrap_key(kek, key, aad=aad)
        return SealedKey(params=KdfParams.bundle_wrap(), wrapped=wrapped)

    def open_key(
        self,
        password: str,
        sealed: SealedKey,
        *,
        aad: bytes,
        failure: str = "wrong_password",
    ) -> bytes:
        if sealed.params.wraps_with_bundle_key:
            raise CryptoError("This key must be opened with the bundle key.", code="unsupported_kdf")
        kek = derive_key(password, sealed.params)
        return unwrap_key(kek, sealed.wrapped, aad=aad, failure=failure)

    def open_wrapped_with_key(
        self,
        kek: bytes,
        sealed: SealedKey,
        *,
        aad: bytes,
        failure: str = "tampered",
    ) -> bytes:
        if not sealed.params.wraps_with_bundle_key:
            raise CryptoError("This key is password-wrapped.", code="unsupported_kdf")
        return unwrap_key(kek, sealed.wrapped, aad=aad, failure=failure)

    def rewrap_key(
        self,
        old_password: str,
        new_password: str,
        sealed: SealedKey,
        *,
        aad: bytes,
    ) -> SealedKey:
        key = self.open_key(old_password, sealed, aad=aad, failure="wrong_password")
        return self.seal_key(new_password, key, aad=aad)
