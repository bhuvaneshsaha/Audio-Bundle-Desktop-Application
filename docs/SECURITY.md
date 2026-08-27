# Security design

Priority: **confidentiality of media**, **integrity of the bundle**, **no plaintext passwords in `project.json` or the `.audiobundle`**. Generate Bundle may write a separate `{bundle}-passwords.txt` next to the encrypted file for independent sharing. This is not consumer DRM. A determined user who can unlock content on their machine can record audio or screenshot PDFs.

## Key hierarchy (envelope encryption)

```text
Main password
    → Argon2id (unique salt, memory-hard params stored in KDFP)
    → KEK_main (32 bytes)
    → AES-256-GCM wrap of random BundleKey

BundleKey
    → encrypts outer manifest (block names/order only)

Each custom-password block
    → Argon2id (per-block salt)
    → KEK_block
    → AES-256-GCM wrap of random BlockKey

Windows-auth and no-password blocks
    → BlockKey wrapped with the BundleKey (AES-256-GCM)
    → Client still requires Windows sign-in for `windows` blocks (access control, not a cryptographic bind to AD)

BlockKey
    → encrypts inner manifest and that block’s file blobs
```

The official Client always asks for Windows credentials before any bundle is opened (shared PCs). Username/password uses `LogonUser`. Windows Hello / PIN / fingerprint verifies the *currently logged-on* user (`UserConsentVerifier`, with the system credential dialog as fallback). Shared kiosks should keep using typed credentials so a different person can sign in.

How Windows-auth blocks differ from custom-password blocks (crypto vs Client gate): [BLOCK_AUTHENTICATION_SECURITY.md](BLOCK_AUTHENTICATION_SECURITY.md). Folder tree and per-day sequence: [COURSE_STRUCTURE.md](COURSE_STRUCTURE.md).

**Active Directory:** the same LogonUser path accepts `DOMAIN\user` and `user@upn`. Allow-lists may include those names or `group:DOMAIN\\Group`. Group membership checks are recorded for AD-joined machines.

This is not consumer DRM. A modified unofficial client that already has the main password can unwrap Windows/no-password blocks without calling LogonUser. Treat Windows auth as a **gate on the shipped Client**, plus an allow-list.

## Client policies (Admin settings)

* **Single active block** (default on for new projects): unlocking a block locks the previous one and deletes its temp files.
* **Sequential unlock** (default on for new projects): block *n* in a folder cannot open until earlier **sibling blocks** in that folder have been opened at least once in this session. Starting another folder does not require finishing the first. Folders are organization only. See [COURSE_STRUCTURE.md](COURSE_STRUCTURE.md).

Old bundles that omit these flags keep the previous behaviour (both off).

## Keyboard shortcuts

The Client lists shortcuts under F1 (play/pause, seek, back, folder/block tree). Intended for keyboard-only and screen-reader use.

Content keys are random. Changing a password later re-wraps keys; it does not require re-encrypting large audio, as long as the BlockKey is retained in memory during Admin generate.

The **main** password must not unwrap block keys. Seeing the course outline after the main password is intended; lesson bytes are not.

## Milestone 2 status

Implemented in `audio_bundle.core.crypto`: Argon2id KDF, AES-256-GCM, envelope wrap/unwrap, AAD binding, SHA-256 verify-after-decrypt. Unit tests use `KdfProfile.TEST` (low memory). Production generate uses 64 MiB Argon2id.

## Algorithms

| Use | Algorithm | Library |
| --- | --- | --- |
| Password KDF | Argon2id | `argon2-cffi` (`hash_secret_raw`, Type.ID) |
| Content & wrapping | AES-256-GCM | `cryptography` (`AESGCM`) |
| Nonces / salts / keys | CSPRNG | `secrets.token_bytes` |

No hand-rolled primitives. No AES-CBC+HMAC invented locally.

Suggested starting Argon2id parameters (tune on real hardware, always run off the UI thread):

* memory: 64 MiB
* time: 3
* parallelism: 1 or 2
* output: 32 bytes

Parameters are stored next to the salt so older bundles remain readable if defaults change.

## Password storage

Never stored in:

* `project.json`
* bundle plaintext headers
* logs
* Qt settings
* temp files
* source

At **Generate Bundle** time the Admin writes a separate `{bundle}-passwords.txt` next to the `.audiobundle`. That file is plaintext on purpose so it can be printed or sent independently of the encrypted course. It is not part of the bundle and is not saved into `project.json`. Treat it like any other password list.

Wrong main or block password: generic failure, no distinction that leaks whether a particular field was tampered vs mistyped **when the wrap blob does not decrypt**. After a successful main unlock, a later GCM failure on `EMAN`/`BLOB` is reported as **corruption/tamper**, not as a wrong password.

## Tamper detection

Fail closed on:

* bad magic / unsupported version
* footer size mismatch
* GCM authentication failure
* inner JSON that fails schema validation
* plaintext SHA-256 mismatch after decrypt
* media type not in the allow-list

Never pass unauthenticated bytes to Qt Multimedia or the PDF view.

## Temporary decryption

Prefer decrypting into memory. If Qt requires a file path, use a process-private temp directory with restrictive permissions and delete on block lock, bundle close, and app exit. Document that OS swap, crash dumps, and media backends may still retain copies.

## Admin project risk

The admin tree contains **plaintext source media**. Treat it as a secret alongside passwords. Only the generated `.audiobundle` is meant for clients.

## Known limitations and risks

1. **Offline brute force.** Anyone with the file can try passwords. Argon2id raises cost; it does not stop a weak password.
2. **Main password oracle vs tamper.** Changing `KDFP`/`WKEY` looks like a wrong password. Acceptable; do not try to be clever with extra unauthenticated checksums that leak state.
3. **Block names leak after main unlock.** By design. Do not put sensitive material only in block titles if that is a concern.
4. **No forward secrecy / no revocation.** Distributing a bundle is like handing over a file. Rotate by issuing a new bundle and new passwords.
5. **Process memory.** Unlocked BlockKeys and plaintext audio exist in RAM while playing.
6. **Clipboard / screenshots / analog hole.** Out of scope.
7. **Dependency and supply chain.** Pin hashes at packaging time (Milestone 8).
8. **Path traversal in projects.** Relative source paths reject `..` and absolute paths (Milestone 1).
9. **Zip confusion.** The format is not ZIP; the client must not fall back to zipfile.

## Testing bar (Milestone 2+)

* Correct password decrypts; incorrect fails
* Bit-flip of ciphertext or AAD fails
* Unique salts in successive generates
* Nonce reuse is impossible in the writer (new nonce every `encrypt` call)
