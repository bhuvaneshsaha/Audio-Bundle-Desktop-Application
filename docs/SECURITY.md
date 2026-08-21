# Security design

This application protects **offline course media** (audio and PDF) inside a single `.audiobundle` file. Priority order: **confidentiality of media**, **integrity of the bundle**, **no plaintext passwords on disk**.

This is **not consumer DRM**. Anyone who can unlock a block on their machine can record the speaker or screenshot a PDF. The design stops casual copying of the bundle file and detects tampering. It does not stop a determined user who already has a valid password.

There is **no server, no account system, and no network call**. Security is entirely local: passwords the author chooses, algorithms in `audio_bundle.core.crypto`, and the on-disk format in [BUNDLE_FORMAT.md](BUNDLE_FORMAT.md).

## Threat model (in scope)

| Attacker | Goal | What we try to stop |
| --- | --- | --- |
| Someone who only has the `.audiobundle` | Read lessons without passwords | Offline guessing is expensive (Argon2id); ciphertext is unreadable without keys |
| Someone who has the main password only | Read lesson audio/PDF | Block keys are wrapped with **different** passwords; outer manifest is outline only |
| Someone who modifies the file | Feed garbage or swapped files into the player | AES-GCM tags, AAD binding, footer length, SHA-256 after decrypt, media allow-list |
| Admin project on a shared disk | Recover author passwords from `project.json` | Passwords are never written there |

## Out of scope

- Preventing screen capture, analog recording, or OS-level memory dumps of a running Client
- Remote attestation, license servers, or “this file only plays on machine X”
- Encrypting the Admin **source** project (plaintext media lives next to `project.json` until Generate Bundle)

## Key hierarchy (envelope encryption)

```text
Main password
    → Argon2id (unique salt + parameters stored in KDFP)
    → KEK_main (32 bytes)
    → AES-256-GCM wrap of a random BundleKey          (chunk WKEY)

BundleKey
    → AES-256-GCM of the outer manifest               (chunk EMAN)
      (title, block names and order only)

Each block password
    → Argon2id (per-block salt in BKDF)
    → KEK_block (32 bytes)
    → AES-256-GCM wrap of a random BlockKey           (chunk BWKY)

BlockKey
    → AES-256-GCM of the inner file list              (chunk BMAN)
    → AES-256-GCM of each media file                  (chunk BLOB)
```

Content keys are random 256-bit values from a CSPRNG. Passwords never encrypt the large audio files directly. Changing a password later can **re-wrap** the same content key (`CryptoEngine.rewrap_key`); the Admin UI does not expose that yet (see Future).

The main password **must not** unwrap block keys. After the main password, the Client may show the course outline. Lesson bytes stay locked until the matching block password.

---

## Security mechanisms

Each row is something the product actually does today. “Future” is optional work, not a commitment.

### 1. Fully offline operation

| | |
| --- | --- |
| **What** | No HTTP client, no cloud KMS, no license check. Admin and Client run on the user’s PC. |
| **Why** | Requirement: internal distribution without accounts or a server. Removes a class of network attacks and data-residency questions. |
| **Alternatives** | A central unlock API, or wrapping keys with a company KMS. Those need connectivity, identity, and an availability story this product does not have. |
| **Future** | Keep offline. If a later version adds optional telemetry or updates, treat that as a new threat model (pin TLS, fail closed when offline). |

### 2. Envelope encryption (password wraps a random content key)

| | |
| --- | --- |
| **What** | Argon2id derives a **key-encryption key (KEK)**. AES-256-GCM wraps a random **BundleKey** or **BlockKey**. Media is encrypted with those content keys, not with the password bytes. |
| **Why** | Passwords are low entropy. A random 256-bit key is the actual file key. Re-keying a password does not require re-encrypting every audio blob if the content key is kept. |
| **Alternatives** | Encrypt files directly with a KDF output (simpler, but password change means re-encrypting everything). Use a KEK wrapping standard such as NIST AES-KW; GCM wrap is already authenticated and matches the rest of the format. |
| **Future** | Admin “change password / re-wrap” without regenerating the bundle, using the existing `rewrap_key` helper. |

### 3. Two-layer passwords (main vs block)

| | |
| --- | --- |
| **What** | Main password opens the bundle and the **outer** manifest. Each block has its own password that opens that block’s **inner** manifest and files. |
| **Why** | Authors can share the course outline (or a weaker “catalogue” password) without giving every lesson. A leaked block password does not unlock other blocks. |
| **Alternatives** | Single password for the whole file (simpler UX, all-or-nothing). Per-file passwords (heavier UX). Public-key wrapping per learner (needs identity infrastructure). |
| **Future** | Optional “same password for all blocks” shortcut in Admin; still store distinct wraps so blocks can diverge later. |

### 4. Argon2id password KDF

| | |
| --- | --- |
| **What** | `argon2-cffi` `hash_secret_raw`, Type.ID, version 19. Production: memory **64 MiB**, time **3**, parallelism **1**, output **32 bytes**, salt **16 random bytes**. Parameters travel with the bundle (`KDFP` / `BKDF`) so old files stay readable if defaults change. Unit tests use `KdfProfile.TEST` only. |
| **Why** | Memory-hard KDF raises the cost of offline guessing on GPUs/ASICs compared with PBKDF2. Argon2id mixes data-dependent and data-independent rounds (side-channel vs TMTO trade-off recommended for password hashing). RFC 9106. |
| **Alternatives** | **scrypt** (also memory-hard; Argon2 is the newer PHC winner). **PBKDF2-HMAC-SHA256** (widely available, cheaper to brute-force). **bcrypt** (64-byte password limit, not a general KDF for 32-byte keys as cleanly). |
| **Future** | Raise memory/time on new bundles after measuring Admin/Client hardware. Reject obviously weak passwords in the UI. Do not silently lower parameters when reading; fail if a record is below a minimum floor. |

### 5. AES-256-GCM authenticated encryption

| | |
| --- | --- |
| **What** | `cryptography` `AESGCM`. 256-bit key, 12-byte random nonce, 16-byte tag. Used for key wraps and for manifests/blobs. |
| **Why** | Confidentiality **and** integrity in one primitive. Hardware AES-NI is common on target PCs. Matches the REQUIREMENTS shortlist. No homegrown CBC+HMAC. |
| **Alternatives** | **ChaCha20-Poly1305** (better on machines without AES-NI; slightly different ecosystem). **AES-256-GCM-SIV** (nonce-misuse resistant; less ubiquitous in Python). |
| **Future** | Format version 2 could offer ChaCha20-Poly1305 as an option; v1 stays AES-GCM. Never reuse a nonce with the same key (writer already draws a fresh nonce per `encrypt`). |

### 6. Unique salts and unique GCM nonces

| | |
| --- | --- |
| **What** | `secrets.token_bytes` for salts, keys, and 12-byte nonces. Every `seal_key` generates a new salt. Every `encrypt` generates a new nonce. |
| **Why** | Same password must not produce the same KEK across bundles/blocks. GCM nonce reuse with one key is catastrophic. |
| **Alternatives** | Counter nonces (safe only if the writer is a single monotonic generator and never forks). Random 96-bit nonces are the usual choice at this volume of encryptions. |
| **Future** | Keep CSPRNG. Tests inject fixed salts/nonces only under an explicit test engine. |

### 7. Associated data (AAD) binding

| | |
| --- | --- |
| **What** | Each GCM blob is bound to: bundle magic, format version, chunk type (`WKEY`, `EMAN`, `BWKY`, `BMAN`, `BLOB`), plus a context (e.g. `"main-wrap"`, block id, blob id). See `bind_aad`. |
| **Why** | Stops splicing a valid ciphertext into another slot (wrong chunk type or wrong block). GCM will fail the tag if AAD does not match. |
| **Alternatives** | Put the same fields inside the plaintext only (weaker: swapping ciphertexts could still decrypt if keys collide). Separate HMAC over the file (more moving parts). |
| **Future** | Include a bundle-id in AAD for every chunk once the outer manifest is known; `WKEY` today uses a fixed main-wrap context because the bundle id is not readable yet. |

### 8. Split manifests (outer vs inner)

| | |
| --- | --- |
| **What** | After the main password the Client sees title and **block names/order** only. Filenames, blob ids, and sizes live in the inner manifest under the block key. |
| **Why** | Least privilege: catalogue without lesson inventory. Avoids putting sensitive titles **only** in block names if that is a concern (names **do** leak after main unlock — by design). |
| **Alternatives** | Encrypt the entire file with one key (no outline). Hide block names too (Client cannot show a list until every block is tried). |
| **Future** | Optional encrypted “cover title” vs public title. |

### 9. Custom `.audiobundle` container (not ZIP)

| | |
| --- | --- |
| **What** | Magic header, length-prefixed chunks, footer with total size. The Client never opens the file with `zipfile`. |
| **Why** | Passworded ZIP is a different (often weak) ecosystem; users might confuse formats. A dedicated layout makes “fail closed” on unknown versions straightforward. |
| **Alternatives** | ZIP + AES, 7z, age, age+tar. Those pull extra parsers and historical crypto mistakes (ZipCrypto). |
| **Future** | Keep the custom format. Document MIME/extension for IT allow-lists. |

### 10. Header CRC-32 and footer length check

| | |
| --- | --- |
| **What** | Header CRC over the first 20 bytes. Last 16 bytes: `ABDLEND\x00` + uint64 file size. Mismatch → fail closed (truncation or append). |
| **Why** | Cheap detection of incomplete copies before spending Argon2 time. Not a substitute for GCM (CRC is not a MAC). |
| **Alternatives** | Skip and rely on GCM only (slower failure). Unauthenticated checksums of ciphertext (can leak; we avoid extra oracles). |
| **Future** | Unchanged. Do not add an unauthenticated “password hint” checksum. |

### 11. Fail-closed authentication and honest error types

| | |
| --- | --- |
| **What** | GCM `InvalidTag` on **key wraps** (`WKEY` / `BWKY`) is reported as a **wrong password** (or invalid data). After a successful unwrap, GCM failure on manifests/blobs is **tamper/corruption**. Empty passwords are rejected. |
| **Why** | Authors and learners need a usable message. We do not try to distinguish “wrong password” vs “tampered wrap” on the wrap itself (those look the same). We do not invent extra unauthenticated checksums that leak state. |
| **Alternatives** | Always say “operation failed” (safer against oracles, worse UX). |
| **Future** | Rate-limit guesses in the Client UI (does not stop a scripted attacker with the file). |

### 12. SHA-256 of plaintext after decrypt

| | |
| --- | --- |
| **What** | Inner manifest stores `plaintext_sha256`. After GCM decrypt, `hmac.compare_digest` checks the hash before the bytes go to Qt. |
| **Why** | Defense in depth if a bug ever returned data without a tag check. Detects Admin/client disagreement on what was packed. **Not** a MAC by itself (the hash is inside authenticated JSON). |
| **Alternatives** | Skip and trust GCM only (reasonable). BLAKE2b (faster; SHA-256 is ubiquitous for reviewers). |
| **Future** | Keep. Do not treat SHA-256 as a password. |

### 13. Media type allow-list

| | |
| --- | --- |
| **What** | Only `.mp3` `.wav` `.m4a` `.aac` and `.pdf`. Type in the manifest must match the filename. The player/viewer never receive other types. |
| **Why** | Reduces the chance of decrypting an unexpected executable or HTML into a viewer. |
| **Alternatives** | Broader media types (more Qt surface). Magic-byte sniffing in addition to extension. |
| **Future** | Optional magic-byte check after decrypt. |

### 14. Passwords never persist on disk

| | |
| --- | --- |
| **What** | Load/save of `project.json` rejects keys such as `password`, `secret`, `key`. Admin block passwords live in **process memory** for the session (block editor + Show password). Main password is entered at Generate Bundle / Client open only. Not written to Qt settings, logs, bundle headers, or temp files. |
| **Why** | A copied Admin folder should not leak passwords. Show password is for verification before generate, not for storage. |
| **Alternatives** | OS keychain / DPAPI for Admin convenience (ties secrets to a login; extra platform code). Encrypted project file (then you still need a master password). |
| **Future** | Optional OS credential store for Admin session restore. Password fields that disable screenshots where the OS allows it. |

### 15. Path traversal controls on Admin projects

| | |
| --- | --- |
| **What** | `relative_source_path` must be relative, no `..`, no absolute/drive paths. Bundle write resolves paths and requires them to stay under the project root. |
| **Why** | Stops a malicious `project.json` from causing the Admin to encrypt `/etc/passwd` or files outside the course. |
| **Alternatives** | Store only content hashes and copy-on-import (already copied into `blocks/`). |
| **Future** | Keep. |

### 16. Atomic bundle write

| | |
| --- | --- |
| **What** | Writer writes `*.audiobundle.tmp` then replaces the destination. |
| **Why** | Crash mid-generate should not leave a truncated file that looks authentic. |
| **Alternatives** | Write in place (risk of half files). |
| **Future** | fsync before replace on POSIX. |

### 17. Process-private temp files for playback

| | |
| --- | --- |
| **What** | Qt Multimedia/PDF generally need a filesystem path. Client decrypts into `tempfile.mkdtemp(prefix="audiobundle-client-")`, directory mode `0700`, files `0600`, random names. Deleted when the bundle is closed or the app exits (`ClientSession.close`). |
| **Why** | Avoid a user-visible “export” folder. Restrictive permissions reduce casual snooping on multi-user UNIX. |
| **Alternatives** | In-memory buffers / QBuffer only (not all Qt backends accept them for audio/PDF). Encrypted pagefile is an OS setting, not ours. |
| **Future** | Overwrite-then-unlink; Windows `FILE_ATTRIBUTE_TEMPORARY`; explore in-memory playback where Qt allows. Document that crash dumps, swap, and the media backend may still retain copies. |

### 18. Crypto only in `core`, KDF off the UI thread

| | |
| --- | --- |
| **What** | Widgets call `ProjectWorkspace` / `ClientSession`. Generate and open run in `QThread`. Production Argon2 uses 64 MiB. |
| **Why** | Avoid UI freezes and keep Qt code from touching raw AES. Reduces the chance of logging secrets in UI helpers. |
| **Alternatives** | Inline crypto in widgets (harder to test). |
| **Future** | Progress for Argon2 on huge generates; already backgrounded. |

### 19. Supply chain of libraries and packages

| | |
| --- | --- |
| **What** | Encryption uses `cryptography` and `argon2-cffi`. Apps can be frozen with PyInstaller. |
| **Why** | No hand-rolled AES. Reviewers can inspect two widely used libraries. |
| **Alternatives** | libsodium/PyNaCl (also sound). Language-native crypto only (worse). |
| **Future** | Pin dependency hashes at packaging time; sign `AudioBundleAdmin.exe` / `AudioBundleClient.exe`; generate an SBOM. |

---

## What is stored where

| Location | Secrets? | Notes |
| --- | --- | --- |
| Admin `project.json` | No passwords, no keys | Names, order, relative paths, optional `autoplay_on_open` |
| Admin `blocks/` | **Plaintext media** | Treat the project folder as sensitive |
| `.audiobundle` plaintext | Magic, version, KDF **parameters and salts**, ciphertext | Salts are not secret; they must be unique |
| Client temp dir | **Plaintext of unlocked files** while open | Removed on close |
| Process RAM | Passwords, KEKs, content keys, plaintext | Unavoidable while playing |

## Known limitations

1. **Offline brute force.** Anyone with the file can try passwords. Argon2id raises cost; a short password still loses.
2. **Wrap oracle vs tamper.** A damaged `KDFP`/`WKEY` looks like a wrong password. Acceptable.
3. **Block names leak after main unlock.** Do not put secrets only in titles.
4. **No revocation / no forward secrecy.** Recalling a bundle means issuing a new file and new passwords. Old copies still open with old passwords.
5. **Analog hole and memory.** Recording, screenshots, and RAM inspection are out of scope.
6. **Admin workstation.** Source files are plaintext. Disk encryption (BitLocker/FileVault) is an operational control, not this app.
7. **Not a ZIP.** Clients must not fall back to zip tools.

## Testing bar

* Correct password decrypts; incorrect fails
* Bit-flip of ciphertext or AAD fails
* Unique salts across successive generates
* New nonce on every `encrypt`
* `project.json` with a `password` field is refused
* Client temp directory is gone after `session.close()`

## Related documents

* [BUNDLE_FORMAT.md](BUNDLE_FORMAT.md) — bytes on disk
* [SEQUENCE_DIAGRAMS.txt](SEQUENCE_DIAGRAMS.txt) — Admin and Client flows for [sequencediagram.org](https://sequencediagram.org/)
* [ARB_SECURITY_QA.md](ARB_SECURITY_QA.md) — review-board questions and answers
