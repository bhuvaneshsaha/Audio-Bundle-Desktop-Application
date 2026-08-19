from __future__ import annotations

import pytest

from audio_bundle.core.crypto import (
    Ciphertext,
    CryptoEngine,
    KdfParams,
    KdfProfile,
    SealedKey,
    bind_aad,
    decrypt,
    derive_key,
    encrypt,
    random_key,
    random_nonce,
    random_salt,
    sha256_hex,
    verify_sha256,
)
from audio_bundle.shared.constants import (
    AAD_CHUNK_BLOB,
    AAD_CHUNK_BLOCK_WRAP,
    AAD_CHUNK_INNER_MANIFEST,
    AAD_CHUNK_MAIN_WRAP,
    AAD_CHUNK_OUTER_MANIFEST,
    AES_KEY_SIZE,
    GCM_NONCE_SIZE,
    KDF_HASH_LEN,
    KDF_MEMORY_KIB,
    KDF_SALT_SIZE,
    KDF_TIME_COST,
)
from audio_bundle.shared.errors import AuthenticationError, CryptoError, ValidationError


def _engine() -> CryptoEngine:
    return CryptoEngine(kdf_profile=KdfProfile.TEST)


def _aad(chunk: bytes = AAD_CHUNK_MAIN_WRAP, context: bytes = b"bundle-test") -> bytes:
    return bind_aad(chunk, context=context)


def test_random_salts_and_keys_are_unique() -> None:
    salts = {random_salt() for _ in range(64)}
    keys = {random_key() for _ in range(64)}
    nonces = {random_nonce() for _ in range(64)}
    assert len(salts) == 64
    assert len(keys) == 64
    assert len(nonces) == 64
    assert all(len(s) == KDF_SALT_SIZE for s in salts)
    assert all(len(k) == AES_KEY_SIZE for k in keys)
    assert all(len(n) == GCM_NONCE_SIZE for n in nonces)


def test_kdf_params_generate_unique_salts() -> None:
    generated = [KdfParams.generate(profile=KdfProfile.TEST) for _ in range(32)]
    assert len({params.salt for params in generated}) == 32
    for params in generated:
        assert params.algorithm == "argon2id"
        assert params.hash_len == KDF_HASH_LEN


def test_production_kdf_policy() -> None:
    params = KdfParams.generate(profile=KdfProfile.PRODUCTION)
    assert params.time_cost == KDF_TIME_COST
    assert params.memory_kib == KDF_MEMORY_KIB
    assert len(params.salt) == KDF_SALT_SIZE
    roundtrip = KdfParams.from_bytes(params.to_bytes())
    assert roundtrip.salt == params.salt
    assert roundtrip.memory_kib == params.memory_kib


def test_derive_key_is_deterministic_for_same_salt() -> None:
    params = KdfParams.generate(profile=KdfProfile.TEST)
    first = derive_key("correct horse", params)
    second = derive_key("correct horse", params)
    other = derive_key("correct horse battery", params)
    assert first == second
    assert len(first) == AES_KEY_SIZE
    assert first != other


def test_empty_password_rejected() -> None:
    params = KdfParams.generate(profile=KdfProfile.TEST)
    with pytest.raises(ValidationError) as exc:
        derive_key("", params)
    assert exc.value.code == "empty_password"


def test_encrypt_decrypt_roundtrip() -> None:
    key = random_key()
    aad = _aad(AAD_CHUNK_OUTER_MANIFEST)
    blob = encrypt(key, b"outer-manifest-json", aad=aad)
    assert decrypt(key, blob, aad=aad) == b"outer-manifest-json"


def test_encrypt_uses_a_fresh_nonce_each_time() -> None:
    key = random_key()
    aad = _aad()
    nonces = [encrypt(key, b"same-plaintext", aad=aad).nonce for _ in range(48)]
    assert len(set(nonces)) == 48


def test_wrong_key_fails_closed() -> None:
    blob = encrypt(random_key(), b"secret", aad=_aad())
    with pytest.raises(AuthenticationError) as exc:
        decrypt(random_key(), blob, aad=_aad(), failure="tampered")
    assert exc.value.code == "tampered"
    assert b"secret" not in bytes(exc.value.message, "utf-8")


def test_modified_ciphertext_fails() -> None:
    key = random_key()
    aad = _aad(AAD_CHUNK_BLOB, context=b"file-1")
    blob = encrypt(key, b"audio-bytes", aad=aad)
    tampered = bytearray(blob.ciphertext)
    tampered[0] ^= 0x01
    broken = Ciphertext(nonce=blob.nonce, ciphertext=bytes(tampered))
    with pytest.raises(AuthenticationError) as exc:
        decrypt(key, broken, aad=aad, failure="tampered")
    assert exc.value.code == "tampered"


def test_modified_nonce_fails() -> None:
    key = random_key()
    aad = _aad()
    blob = encrypt(key, b"audio-bytes", aad=aad)
    nonce = bytearray(blob.nonce)
    nonce[0] ^= 0x01
    broken = Ciphertext(nonce=bytes(nonce), ciphertext=blob.ciphertext)
    with pytest.raises(AuthenticationError):
        decrypt(key, broken, aad=aad)


def test_modified_aad_fails() -> None:
    key = random_key()
    blob = encrypt(key, b"manifest", aad=_aad(AAD_CHUNK_OUTER_MANIFEST, context=b"bundle-a"))
    with pytest.raises(AuthenticationError) as exc:
        decrypt(key, blob, aad=_aad(AAD_CHUNK_INNER_MANIFEST, context=b"bundle-a"))
    assert exc.value.code == "tampered"


def test_truncated_ciphertext_rejected() -> None:
    with pytest.raises(CryptoError) as exc:
        Ciphertext.from_bytes(b"\x00" * 10)
    assert exc.value.code == "truncated_ciphertext"


def test_password_wrap_roundtrip() -> None:
    engine = _engine()
    bundle_key = engine.new_content_key()
    aad = _aad(AAD_CHUNK_MAIN_WRAP, context=b"course-id")
    sealed = engine.seal_key("main-password", bundle_key, aad=aad)
    opened = engine.open_key("main-password", sealed, aad=aad)
    assert opened == bundle_key
    restored = SealedKey.from_bytes(sealed.to_bytes())
    assert engine.open_key("main-password", restored, aad=aad) == bundle_key


def test_incorrect_password_fails_without_leaking_secret() -> None:
    engine = _engine()
    secret = b"this-must-not-appear-in-errors"
    # wrap a content key, not the secret phrase, but include phrase in password
    password = "correct-password-with-hunter2"
    sealed = engine.seal_key(password, engine.new_content_key(), aad=_aad())
    with pytest.raises(AuthenticationError) as exc:
        engine.open_key("wrong-password", sealed, aad=_aad(), failure="wrong_password")
    assert exc.value.code == "wrong_password"
    text = str(exc.value).lower()
    assert "hunter2" not in text
    assert "correct-password" not in text
    assert secret.decode() not in text


def test_main_password_cannot_open_block_key() -> None:
    engine = _engine()
    block_key = engine.new_content_key()
    block_aad = _aad(AAD_CHUNK_BLOCK_WRAP, context=b"block-1")
    sealed = engine.seal_key("block-password", block_key, aad=block_aad)
    with pytest.raises(AuthenticationError):
        engine.open_key("main-password", sealed, aad=block_aad, failure="wrong_password")


def test_rewrapping_password_keeps_the_same_content_key() -> None:
    engine = _engine()
    aad = _aad(AAD_CHUNK_BLOCK_WRAP, context=b"block-1")
    key = engine.new_content_key()
    sealed = engine.seal_key("old-secret", key, aad=aad)
    resealed = engine.rewrap_key("old-secret", "new-secret", sealed, aad=aad)
    assert engine.open_key("new-secret", resealed, aad=aad) == key
    with pytest.raises(AuthenticationError):
        engine.open_key("old-secret", resealed, aad=aad)


def test_content_hash_detects_swap_after_decrypt() -> None:
    payload = b"pdf-bytes"
    digest = sha256_hex(payload)
    verify_sha256(payload, digest)
    with pytest.raises(AuthenticationError) as exc:
        verify_sha256(b"other-bytes", digest)
    assert exc.value.code == "content_hash_mismatch"


def test_empty_plaintext_is_allowed_for_empty_blocks() -> None:
    key = random_key()
    aad = _aad(AAD_CHUNK_INNER_MANIFEST)
    blob = encrypt(key, b"", aad=aad)
    assert decrypt(key, blob, aad=aad) == b""


def test_kdf_rejects_undersized_salt() -> None:
    with pytest.raises(CryptoError) as exc:
        KdfParams(
            algorithm="argon2id",
            time_cost=1,
            memory_kib=32,
            parallelism=1,
            salt=b"short",
        )
    assert exc.value.code == "invalid_salt"
