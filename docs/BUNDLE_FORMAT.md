# `.audiobundle` format (version 1)

This is the contracted layout for Milestone 3. Milestone 1 only defines the logical manifests that will be serialized inside encrypted chunks.

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

Unknown chunk types with the “critical” flag set must fail the read. Optional chunks may be skipped **only after** the outer manifest is authenticated, and never for crypto-critical types.

Planned chunk types:

| Type | Encrypted | Purpose |
| --- | --- | --- |
| `KDFP` | no | Argon2id parameters + 16-byte salt for the **main** password |
| `WKEY` | AEAD | Bundle key wrapped with KEK derived from the main password |
| `EMAN` | AEAD | Outer `BundleManifest` JSON (UTF-8) |
| `BKDF` | no | Per-block Argon2id parameters + salt (one chunk per block, or packed) |
| `BWKY` | AEAD | Block key wrapped with KEK from the **block** password |
| `BMAN` | AEAD | Inner `BundleBlockContents` JSON |
| `BLOB` | AEAD | One media file ciphertext |
| `FEND` | no | End marker before footer |

Associated data (AAD) for every AES-256-GCM blob binds:

* `format_version`
* chunk type
* bundle id (once known; for `WKEY` use a fixed AAD of magic + version + “main-wrap”)

This prevents splicing a valid ciphertext into the wrong slot.

## Logical JSON (encrypted)

Outer manifest (`EMAN`) — **no filenames, no blob ids**:

```json
{
  "format_version": 1,
  "bundle_id": "uuid",
  "title": "Course Name",
  "created_at": "2026-01-15T12:00:00+00:00",
  "blocks": [
    { "id": "uuid", "name": "Introduction", "order": 0 }
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
