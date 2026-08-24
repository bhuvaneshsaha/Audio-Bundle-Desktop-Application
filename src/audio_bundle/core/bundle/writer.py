from __future__ import annotations

from pathlib import Path

from audio_bundle.core.bundle.format import (
    AAD_MAIN_WRAP_CONTEXT,
    AAD_OUTER_MANIFEST_CONTEXT,
    CHUNK_BKDF,
    CHUNK_BMAN,
    CHUNK_BLOB,
    CHUNK_BWKY,
    CHUNK_EMAN,
    CHUNK_FEND,
    CHUNK_KDFP,
    CHUNK_WKEY,
    build_footer,
    build_header,
    encode_chunk,
    encode_json,
)
from audio_bundle.core.crypto.aad import bind_aad
from audio_bundle.core.crypto.aead import encrypt
from audio_bundle.core.crypto.engine import CryptoEngine
from audio_bundle.core.crypto.hashing import sha256_hex
from audio_bundle.core.models.auth_method import BlockAuthMethod
from audio_bundle.core.models.manifest import BundleBlockContents, BundleFileEntry, BundleManifest
from audio_bundle.core.models.project import Project
from audio_bundle.shared.constants import (
    AAD_CHUNK_BLOB,
    AAD_CHUNK_BLOCK_WRAP,
    AAD_CHUNK_INNER_MANIFEST,
    AAD_CHUNK_MAIN_WRAP,
    AAD_CHUNK_OUTER_MANIFEST,
)
from audio_bundle.shared.errors import BundleError, ValidationError


def _resolve_source(source_root: Path, relative_path: str) -> Path:
    root = source_root.resolve()
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root):
        raise ValidationError("Source path must stay inside the project directory.", code="path_traversal")
    return path


def _load_sources(project: Project, source_root: Path) -> dict[str, bytes]:
    loaded: dict[str, bytes] = {}
    for block in project.blocks:
        for item in block.items:
            path = _resolve_source(source_root, item.relative_source_path)
            try:
                loaded[item.id] = path.read_bytes()
            except FileNotFoundError as exc:
                raise BundleError(
                    f"Missing source file for '{item.display_name}'.",
                    code="missing_source_file",
                ) from exc
            except OSError as exc:
                raise BundleError(
                    f"Could not read '{item.display_name}'.",
                    code="source_read_error",
                ) from exc
    return loaded


def _require_block_passwords(project: Project, block_passwords: dict[str, str]) -> None:
    missing = [
        block.name
        for block in project.blocks
        if project.block_auth_method is BlockAuthMethod.PASSWORD and not block_passwords.get(block.id)
    ]
    if missing:
        raise ValidationError(
            "A password is required for every custom-password block before generating a bundle.",
            code="missing_block_password",
        )
    extra = set(block_passwords) - {block.id for block in project.blocks}
    if extra:
        raise ValidationError("Block passwords include an unknown block.", code="unknown_block_password")


def write_bundle(
    project: Project,
    output_path: Path,
    *,
    main_password: str,
    block_passwords: dict[str, str],
    source_root: Path,
    engine: CryptoEngine | None = None,
) -> BundleManifest:
    """Write a single .audiobundle file. Passwords are never stored."""
    _require_block_passwords(project, block_passwords)
    sources = _load_sources(project, source_root)
    crypto = engine or CryptoEngine()
    manifest = BundleManifest.from_project(project)

    bundle_key = crypto.new_content_key()
    sealed_bundle = crypto.seal_key(
        main_password,
        bundle_key,
        aad=bind_aad(AAD_CHUNK_MAIN_WRAP, context=AAD_MAIN_WRAP_CONTEXT),
    )
    encrypted_manifest = encrypt(
        bundle_key,
        encode_json(manifest.to_dict()),
        aad=bind_aad(AAD_CHUNK_OUTER_MANIFEST, context=AAD_OUTER_MANIFEST_CONTEXT),
    )

    parts = [
        build_header(),
        encode_chunk(CHUNK_KDFP, sealed_bundle.params.to_bytes()),
        encode_chunk(CHUNK_WKEY, sealed_bundle.wrapped.to_bytes()),
        encode_chunk(CHUNK_EMAN, encrypted_manifest.to_bytes()),
    ]

    for block in project.blocks:
        block_key = crypto.new_content_key()
        block_context = block.id.encode("utf-8")
        wrap_aad = bind_aad(AAD_CHUNK_BLOCK_WRAP, context=block_context)
        if project.block_auth_method is BlockAuthMethod.PASSWORD:
            sealed_block = crypto.seal_key(block_passwords[block.id], block_key, aad=wrap_aad)
        else:
            sealed_block = crypto.wrap_with_key(bundle_key, block_key, aad=wrap_aad)
        files: list[BundleFileEntry] = []
        blob_chunks: list[bytes] = []
        for item in block.items:
            plaintext = sources[item.id]
            entry = BundleFileEntry(
                id=item.id,
                display_name=item.display_name,
                original_filename=item.original_filename,
                media_type=item.media_type,
                order=item.order,
                size_bytes=len(plaintext),
                plaintext_sha256=sha256_hex(plaintext),
            )
            files.append(entry)
            encrypted_blob = encrypt(
                block_key,
                plaintext,
                aad=bind_aad(AAD_CHUNK_BLOB, context=entry.blob_id.encode("utf-8")),
            )
            blob_chunks.append(encode_chunk(CHUNK_BLOB, encrypted_blob.to_bytes()))
        inner = BundleBlockContents(block_id=block.id, name=block.name, files=files)
        encrypted_inner = encrypt(
            block_key,
            encode_json(inner.to_dict()),
            aad=bind_aad(AAD_CHUNK_INNER_MANIFEST, context=block_context),
        )
        parts.extend(
            [
                encode_chunk(CHUNK_BKDF, sealed_block.params.to_bytes()),
                encode_chunk(CHUNK_BWKY, sealed_block.wrapped.to_bytes()),
                encode_chunk(CHUNK_BMAN, encrypted_inner.to_bytes()),
                *blob_chunks,
            ]
        )

    parts.append(encode_chunk(CHUNK_FEND, b""))
    body = b"".join(parts)
    payload = body + build_footer(len(body) + 16)

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = destination.with_name(destination.name + ".tmp")
    try:
        tmp_path.write_bytes(payload)
        tmp_path.replace(destination)
    except OSError as exc:
        tmp_path.unlink(missing_ok=True)
        raise BundleError("Could not write the bundle file.", code="bundle_write_error") from exc
    return manifest
