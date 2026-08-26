# `.audiobundle` format (version 1)

This is the implemented layout for format version 1.

Integers are **little-endian**. The file is a magic header, a sequence of length-prefixed chunks, and a footer used to detect truncation.

## Magic

```text
offset 0   16 bytes   b"AUDIOBUNDLE\x00\x00\x00\x00\x00"
offset 16   2 bytes   format_version (uint16) = 1
offset 18   2 bytes   flags (uint16) = 0
offset 20   4 bytes   header_crc32 of bytes [0, 20)  (detects truncated/garbled prefix)
```

Unsupported `format_version` is a hard failure. No attempt to parse payload.

## Chunks

Each chunk:

```text
4 bytes   type (ASCII, e.g. "KDFP")
2 bytes   flags
4 bytes   payload_length (uint32)
N bytes   payload
```

Unknown chunk types with the “critical” flag set must fail the read. Version 1 writes every chunk as critical; unknown types are rejected.

| Type | Encrypted | Purpose |
| --- | --- | --- |
| `KDFP` | no | Argon2id parameters + salt for the **main** password |
| `WKEY` | AEAD | Bundle key wrapped with the main-password KEK |
| `EMAN` | AEAD | Outer `BundleManifest` JSON (UTF-8, compact, sorted keys) |
| `BKDF` | no | Argon2id parameters + salt for a **custom-password** block, or `BNDL` record when the block key is wrapped by the bundle key |
| `BWKY` | AEAD | Block key wrapped with the block KEK **or** the bundle key |
| `BMAN` | AEAD | Inner `BundleBlockContents` JSON |
| `BLOB` | AEAD | One media file (`nonce || ciphertext || tag`) |
| `FEND` | no | End marker before footer |

Chunk order:

```text
KDFP, WKEY, EMAN,
(BKDF, BWKY, BMAN, BLOB*)*,
FEND
```

Block groups follow the outer manifest order. `BLOB` chunks for a block follow that block’s inner file order. `BLOB` payload is AEAD ciphertext only (`nonce || ciphertext || tag`).

AAD (via `bind_aad`) is:

```text
BUNDLE_MAGIC || uint16 format_version || chunk_type || context
```

| Chunk | Context |
| --- | --- |
| `WKEY` | `main-wrap` |
| `EMAN` | `outer-manifest` |
| `BWKY` / `BMAN` | UTF-8 block id |
| `BLOB` | UTF-8 blob id |

This prevents splicing a valid ciphertext into the wrong slot.

## Logical JSON (encrypted)

Outer manifest (`EMAN`) — **no filenames, no blob ids**:

```json
{
  "format_version": 1,
  "bundle_id": "uuid",
  "title": "Course Name",
  "created_at": "2026-01-15T12:00:00+00:00",
  "autoplay_on_open": false,
  "single_active_block": true,
  "sequential_unlock": true,
  "block_auth_method": "password",
  "windows_principals": [],
  "folders": [
    { "id": "uuid", "parent_id": null, "name": "Day 1", "node_type": "folder", "sort_order": 0 }
  ],
  "blocks": [
    { "id": "uuid", "parent_id": "uuid", "name": "Introduction", "order": 0, "auth_method": "password" }
  ]
}
```

Inner block manifest (`BMAN`):

```json
{
  "block_id": "uuid",
  "name": "Introduction",
  "files": [
    {
      "id": "uuid",
      "blob_id": "uuid",
      "display_name": "Welcome audio",
      "original_filename": "welcome.mp3",
      "media_type": "audio",
      "order": 0,
      "size_bytes": 12345,
      "plaintext_sha256": "hex"
    }
  ]
}
```

File order in `files` is the Admin order. Clients must not re-sort.

## Footer (truncation)

Last 16 bytes:

```text
8 bytes   b"ABDLEND\x00"
8 bytes   total file size as uint64
```

If size does not match, the file is truncated or appended to. Fail closed.

## Determinism for tests

Given fixed:

* passwords
* salts / keys / nonces (injected in tests)
* manifest JSON (compact separators, UTF-8, sorted keys optional but documented)

the writer should emit a byte-for-byte stable file. Production uses CSPRNG for salts, keys, and 12-byte GCM nonces.

## What the client must never do

* Treat a ZIP (passworded or not) as a bundle
* Decode ciphertext after a failed authentication tag
* Play or render bytes that failed SHA-256 after decrypt
* Open a file whose `media_type` is not `audio` or `pdf`
