# Architecture

Shared `core` holds models, validation, crypto, bundle I/O, and the Admin `ProjectWorkspace`. Qt widgets call those APIs and do not encrypt or parse bundle bytes.

## Package layout

```text
src/audio_bundle/
├── admin/                 # Qt Admin UI (Milestone 4)
├── client/                # Qt Client UI (Milestone 5–7)
├── core/
│   ├── models/            # Project, Block, MediaItem, BundleManifest
│   ├── validation/        # Field and graph checks (no Qt)
│   ├── storage/           # Admin project.json read/write
│   ├── crypto/            # KDF + AEAD (Milestone 2)
│   └── bundle/            # Reader/writer (Milestone 3)
└── shared/                # Constants, errors, small helpers
```

Business rules live in `core/`. Qt widgets will call those APIs; they will not parse bundles or encrypt bytes themselves.

## Roles

| Surface | Responsibility |
| --- | --- |
| Admin project | Editable, unencrypted source tree + `project.json`. Re-openable. |
| `.audiobundle` | Single distributable file. Encrypted. Clients never need source files. |
| Client | Opens a bundle, authenticates, plays audio, shows PDFs. |

Admin and Client share `core` and can be packaged as two PyInstaller entry points.

## Data models (Milestone 1)

### `Project`

Editable admin document: name, timestamps, a single level of day folders (Day 1, Day 2, …) and `Block` list. Schema versioned (`PROJECT_SCHEMA_VERSION`). Folders are labels only. Block sequence is scoped to the immediate parent folder.

### `Folder` / `Block` (nodes)

Each node has `id`, `parent_id` (null for day folders; blocks point at a day), `name`, `node_type` (`folder` \| `block`), and sibling `order` / `sort_order`. Folders are a **single top level**, defaulting to **Day 1, Day 2, …**, and may be renamed to anything (`AGDF.21`, `Maintenance`, …). Names never change hierarchy or sequencing.

### `Block`

Named ordered list of `MediaItem`. **Passwords are not fields on this model.** They are supplied at bundle generation (Milestone 3/4) and used only to wrap random block keys.

### `MediaItem`

One imported file: display name, original filename, relative source path, `MediaType` (`audio` \| `pdf`), order, optional size and SHA-256 of the source file.

Order is an explicit contiguous index (`0..n-1`). Nothing sorts by filename.

### `BundleManifest` (outer)

What the client may read after the **main** password: title, policies, folders, and `BundleBlockSummary` (id, parent, name, sibling order, auth method). **No file list.** Folders have no lock or sequence.

### `BundleBlockContents` (inner)

What the client may read after a **block** password: file entries in admin order, media types, sizes, blob ids.

`ordered_audio_files()` skips PDFs so sequential playback can walk audio items without treating documents as tracks.

## Admin project on disk

```text
MyCourse/
├── project.json
├── blocks/
│   ├── block-001/   # source files copied or referenced relatively
│   └── block-002/
└── output/
    └── MyCourse.audiobundle
```

`project.json` is UTF-8 JSON. Load/save reject any password/secret keys.

## Threading

KDF, encryption, import, and bundle write run off the GUI thread (`QThread` workers). Models themselves are plain dataclasses.

## Crypto (Milestone 2)

Implemented in `audio_bundle.core.crypto`, independent of Qt:

* Argon2id password KDF (`KdfProfile.PRODUCTION` vs `TEST`)
* AES-256-GCM with random 12-byte nonces and bound AAD
* Envelope wrap of random bundle/block keys
* SHA-256 check for plaintext after decrypt

## Bundle I/O (Milestone 3)

`audio_bundle.core.bundle.write_bundle` / `open_bundle` produce a single encrypted file. Tests and later UI should call these APIs rather than parsing bytes in widgets.

## Admin UI (Milestone 4)

`audio_bundle.admin` is a PySide6 app. `ProjectWorkspace` copies imported files into `blocks/<block-id>/`, saves `project.json`, and calls `write_bundle` from a worker thread. Unlock method (custom password, Windows authentication, or none) is a **project** setting applied to every block. Client policies (one block at a time, sequential open **within each folder**) are project settings. Passwords are session-only.

## Client UI (Milestone 5)

`audio_bundle.client` requires a Windows sign-in (username/password or Hello/PIN/fingerprint for the current user) before opening a bundle. It then opens the bundle on a worker thread, shows the folder/block tree, unlocks using the course-wide method, and decrypts selected files into a process-private temp directory. Keyboard shortcuts are listed with F1.

## Client playback (Milestones 6–7)

Sequential audio order is computed in `audio_bundle.core.playback` (PDFs are not tracks). The Client `AudioPlayer` and `PdfViewer` widgets provide transport, speed, volume, page navigation, zoom, and search. Temp files are still cleaned up by `ClientSession`.

## Packaging (Milestone 8)

`packaging/admin.spec` and `packaging/client.spec` produce windowed one-file binaries via PyInstaller.
