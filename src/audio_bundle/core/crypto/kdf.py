from __future__ import annotations

from enum import StrEnum

from argon2.exceptions import HashingError
from argon2.low_level import Type, hash_secret_raw

from audio_bundle.core.crypto.random import random_salt
from audio_bundle.shared.constants import (
    KDF_ALGORITHM,
    KDF_BUNDLE_WRAP,
    KDF_HASH_LEN,
    KDF_MEMORY_KIB,
    KDF_PARALLELISM,
    KDF_SALT_SIZE,
    KDF_TIME_COST,
    MAX_PASSWORD_BYTES,
    TEST_KDF_MEMORY_KIB,
    TEST_KDF_PARALLELISM,
    TEST_KDF_TIME_COST,
)
from audio_bundle.shared.errors import CryptoError, ValidationError

ARGON2_VERSION = 19
_KDF_RECORD_MAGIC = b"ARG2"
_BUNDLE_WRAP_MAGIC = b"BNDL"


class KdfProfile(StrEnum):
    PRODUCTION = "production"
    TEST = "test"


def encode_password(password: str) -> bytes:
    if not isinstance(password, str):
        raise ValidationError("Password must be a string.", code="invalid_password")
    if password == "":
        raise ValidationError("Password is required.", code="empty_password")
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise ValidationError("Password is too long.", code="password_too_long")
    return encoded


class KdfParams:
    __slots__ = ("algorithm", "time_cost", "memory_kib", "parallelism", "salt", "hash_len")

    def __init__(
        self,
        *,
        algorithm: str,
        time_cost: int,
        memory_kib: int,
        parallelism: int,
        salt: bytes,
        hash_len: int = KDF_HASH_LEN,
    ) -> None:
        if algorithm not in {KDF_ALGORITHM, KDF_BUNDLE_WRAP}:
            raise CryptoError(f"Unsupported KDF '{algorithm}'.", code="unsupported_kdf")
        if time_cost < 1 or memory_kib < 8 or parallelism < 1:
            raise CryptoError("KDF parameters are too weak or invalid.", code="invalid_kdf_params")
        if hash_len != KDF_HASH_LEN:
            raise CryptoError("KDF output length must be 32 bytes.", code="invalid_kdf_params")
        if not isinstance(salt, (bytes, bytearray)) or len(salt) != KDF_SALT_SIZE:
            raise CryptoError("KDF salt must be 16 random bytes.", code="invalid_salt")
        self.algorithm = algorithm
        self.time_cost = int(time_cost)
        self.memory_kib = int(memory_kib)
        self.parallelism = int(parallelism)
        self.salt = bytes(salt)
        self.hash_len = int(hash_len)

    @classmethod
    def generate(cls, *, profile: KdfProfile = KdfProfile.PRODUCTION) -> KdfParams:
        if profile is KdfProfile.TEST:
            time_cost, memory_kib, parallelism = (
                TEST_KDF_TIME_COST,
                TEST_KDF_MEMORY_KIB,
                TEST_KDF_PARALLELISM,
            )
        elif profile is KdfProfile.PRODUCTION:
            time_cost, memory_kib, parallelism = KDF_TIME_COST, KDF_MEMORY_KIB, KDF_PARALLELISM
        else:
            raise CryptoError("Unknown KDF profile.", code="invalid_kdf_params")
        return cls(
            algorithm=KDF_ALGORITHM,
            time_cost=time_cost,
            memory_kib=memory_kib,
            parallelism=parallelism,
            salt=random_salt(),
        )

    @classmethod
    def bundle_wrap(cls) -> KdfParams:
        return cls(
            algorithm=KDF_BUNDLE_WRAP,
            time_cost=1,
            memory_kib=8,
            parallelism=1,
            salt=b"\x00" * KDF_SALT_SIZE,
        )

    @property
    def wraps_with_bundle_key(self) -> bool:
        return self.algorithm == KDF_BUNDLE_WRAP

    def to_bytes(self) -> bytes:
        magic = _BUNDLE_WRAP_MAGIC if self.wraps_with_bundle_key else _KDF_RECORD_MAGIC
        return (
            magic
            + bytes([ARGON2_VERSION, self.hash_len, len(self.salt)])
            + self.time_cost.to_bytes(4, "little")
            + self.memory_kib.to_bytes(4, "little")
            + self.parallelism.to_bytes(4, "little")
            + self.salt
        )

    @classmethod
    def from_bytes(cls, payload: bytes) -> KdfParams:
        if len(payload) < 16 + KDF_SALT_SIZE:
            raise CryptoError("KDF record is invalid.", code="invalid_kdf_record")
        magic = payload[:4]
        if magic == _BUNDLE_WRAP_MAGIC:
            algorithm = KDF_BUNDLE_WRAP
        elif magic == _KDF_RECORD_MAGIC:
            algorithm = KDF_ALGORITHM
        else:
            raise CryptoError("KDF record is invalid.", code="invalid_kdf_record")
        version, hash_len, salt_len = payload[4], payload[5], payload[6]
        if version != ARGON2_VERSION or salt_len != KDF_SALT_SIZE:
            raise CryptoError("Unsupported KDF record.", code="unsupported_kdf")
        time_cost = int.from_bytes(payload[7:11], "little")
        memory_kib = int.from_bytes(payload[11:15], "little")
        parallelism = int.from_bytes(payload[15:19], "little")
        salt = payload[19 : 19 + salt_len]
        if len(payload) != 19 + salt_len:
            raise CryptoError("KDF record is truncated or has trailing data.", code="invalid_kdf_record")
        return cls(
            algorithm=algorithm,
            time_cost=time_cost,
            memory_kib=memory_kib,
            parallelism=parallelism,
            salt=salt,
            hash_len=hash_len,
        )


def derive_key(password: str, params: KdfParams) -> bytes:
    if params.wraps_with_bundle_key:
        raise CryptoError("This key is wrapped by the bundle key, not a password.", code="unsupported_kdf")
    secret = encode_password(password)
    try:
        return hash_secret_raw(
            secret=secret,
            salt=params.salt,
            time_cost=params.time_cost,
            memory_cost=params.memory_kib,
            parallelism=params.parallelism,
            hash_len=params.hash_len,
            type=Type.ID,
            version=ARGON2_VERSION,
        )
    except HashingError as exc:
        raise CryptoError("Password derivation failed.", code="kdf_failed") from exc
