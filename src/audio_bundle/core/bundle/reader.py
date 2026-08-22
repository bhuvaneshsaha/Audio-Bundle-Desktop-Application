from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from audio_bundle.core.bundle.format import (
    AAD_MAIN_WRAP_CONTEXT,
    AAD_OUTER_MANIFEST_CONTEXT,
    decode_json,
    parse_container,
)
from audio_bundle.core.bundle.layout import BlockRegion, ParsedBundle, group_chunks
from audio_bundle.core.crypto.aad import bind_aad
from audio_bundle.core.crypto.aead import Ciphertext, decrypt
from audio_bundle.core.crypto.engine import CryptoEngine, SealedKey
from audio_bundle.core.crypto.hashing import verify_sha256
from audio_bundle.core.crypto.kdf import KdfParams
from audio_bundle.core.models.manifest import BundleBlockContents, BundleBlockSummary, BundleFileEntry, BundleManifest
from audio_bundle.shared.constants import (
    AAD_CHUNK_BLOB,
    AAD_CHUNK_BLOCK_WRAP,
    AAD_CHUNK_INNER_MANIFEST,
    AAD_CHUNK_MAIN_WRAP,
    AAD_CHUNK_OUTER_MANIFEST,
)
from audio_bundle.shared.errors import AuthenticationError, BundleError, ValidationError


def _sealed(kdf_payload: bytes, wrapped_payload: bytes) -> SealedKey:
    return SealedKey(params=KdfParams.from_bytes(kdf_payload), wrapped=Ciphertext.from_bytes(wrapped_payload))


def _open_manifest(engine: CryptoEngine, parsed: ParsedBundle, main_password: str) -> tuple[bytes, BundleManifest]:
    bundle_key = engine.open_key(
        main_password,
        _sealed(parsed.main_kdf, parsed.wrapped_bundle_key),
        aad=bind_aad(AAD_CHUNK_MAIN_WRAP, context=AAD_MAIN_WRAP_CONTEXT),
        failure="wrong_password",
    )
    plaintext = decrypt(
        bundle_key,
        Ciphertext.from_bytes(parsed.encrypted_manifest),
        aad=bind_aad(AAD_CHUNK_OUTER_MANIFEST, context=AAD_OUTER_MANIFEST_CONTEXT),
        failure="tampered",
    )
    try:
        manifest = BundleManifest.from_dict(decode_json(plaintext))
    except ValidationError as exc:
        raise AuthenticationError("The bundle manifest is invalid.", code="invalid_manifest") from exc
    if len(parsed.blocks) != len(manifest.blocks):
        raise AuthenticationError("The bundle structure does not match the manifest.", code="tampered")
    return bundle_key, manifest


@dataclass(slots=True)
class UnlockedBlock:
    contents: BundleBlockContents
    _key: bytes
    _blobs: list[bytes]

    def read_file(self, file_id: str) -> bytes:
        for index, entry in enumerate(self.contents.files):
            if entry.id == file_id:
                return self._decrypt_entry(index, entry)
        raise BundleError("File not found in this block.", code="item_not_found")

    def read_file_at(self, index: int) -> bytes:
        try:
            entry = self.contents.files[index]
        except IndexError as exc:
            raise BundleError("File not found in this block.", code="item_not_found") from exc
        return self._decrypt_entry(index, entry)

    def _decrypt_entry(self, index: int, entry: BundleFileEntry) -> bytes:
        if index >= len(self._blobs):
            raise AuthenticationError("The bundle is missing encrypted file data.", code="tampered")
        plaintext = decrypt(
            self._key,
            Ciphertext.from_bytes(self._blobs[index]),
            aad=bind_aad(AAD_CHUNK_BLOB, context=entry.blob_id.encode("utf-8")),
            failure="tampered",
        )
        if len(plaintext) != entry.size_bytes:
            raise AuthenticationError("Decrypted file size does not match the manifest.", code="tampered")
        if not entry.plaintext_sha256:
            raise AuthenticationError("Integrity hash is missing or invalid.", code="invalid_content_hash")
        verify_sha256(plaintext, entry.plaintext_sha256)
        return plaintext


@dataclass(slots=True)
class OpenedBundle:
    path: Path
    manifest: BundleManifest
    _engine: CryptoEngine
    _parsed: ParsedBundle
    _bundle_key: bytes

    def unlock_block(self, block_id: str, password: str | None = None) -> UnlockedBlock:
        for index, summary in enumerate(self.manifest.blocks):
            if summary.id == block_id:
                return self._unlock_region(index, summary, password)
        raise BundleError("Block not found in this bundle.", code="block_not_found")

    def _unlock_region(self, index: int, summary: BundleBlockSummary, password: str | None) -> UnlockedBlock:
        block_id = summary.id
        region: BlockRegion = self._parsed.blocks[index]
        block_context = block_id.encode("utf-8")
        sealed = _sealed(region.kdf, region.wrapped_key)
        wrap_aad = bind_aad(AAD_CHUNK_BLOCK_WRAP, context=block_context)
        if sealed.params.wraps_with_bundle_key:
            block_key = self._engine.open_wrapped_with_key(
                self._bundle_key,
                sealed,
                aad=wrap_aad,
                failure="tampered",
            )
        else:
            if not password:
                raise AuthenticationError(
                    "The password is incorrect or the data is not valid.",
                    code="wrong_password",
                )
            block_key = self._engine.open_key(
                password,
                sealed,
                aad=wrap_aad,
                failure="wrong_password",
            )
        plaintext = decrypt(
            block_key,
            Ciphertext.from_bytes(region.encrypted_manifest),
            aad=bind_aad(AAD_CHUNK_INNER_MANIFEST, context=block_context),
            failure="tampered",
        )
        try:
            contents = BundleBlockContents.from_dict(decode_json(plaintext))
        except ValidationError as exc:
            raise AuthenticationError("The block manifest is invalid.", code="invalid_manifest") from exc
        if contents.block_id != block_id:
            raise AuthenticationError("The block manifest does not match this block.", code="tampered")
        if len(region.encrypted_blobs) != len(contents.files):
            raise AuthenticationError("The bundle file list does not match stored data.", code="tampered")
        return UnlockedBlock(contents=contents, _key=block_key, _blobs=region.encrypted_blobs)


def open_bundle(
    path: Path,
    main_password: str,
    *,
    engine: CryptoEngine | None = None,
) -> OpenedBundle:
    bundle_path = Path(path)
    try:
        data = bundle_path.read_bytes()
    except OSError as exc:
        raise BundleError("Could not read the bundle file.", code="bundle_read_error") from exc
    _, chunks = parse_container(data)
    parsed = group_chunks(chunks)
    crypto = engine or CryptoEngine()
    bundle_key, manifest = _open_manifest(crypto, parsed, main_password)
    return OpenedBundle(
        path=bundle_path,
        manifest=manifest,
        _engine=crypto,
        _parsed=parsed,
        _bundle_key=bundle_key,
    )
