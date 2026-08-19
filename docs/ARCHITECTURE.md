# Architecture

Milestone 1 defines the package layout and in-memory models. UI, cryptography, and `.audiobundle` I/O are intentionally not implemented yet.

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

Editable admin document: name, timestamps, ordered `Block` list. Schema versioned (`PROJECT_SCHEMA_VERSION`).

### `Block`

Named ordered list of `MediaItem`. **Passwords are not fields on this model.** They are supplied at bundle generation (Milestone 3/4) and used only to wrap random block keys.

### `MediaItem`

One imported file: display name, original filename, relative source path, `MediaType` (`audio` \| `pdf`), order, optional size and SHA-256 of the source file.

Order is an explicit contiguous index (`0..n-1`). Nothing sorts by filename.

### `BundleManifest` (outer)

What the client may read after the **main** password: title, bundle id, format version, and `BundleBlockSummary` (id, name, order). **No file list.**

### `BundleBlockContents` (inner)

What the client may read after a **block** password: file entries in admin order, media types, sizes, blob ids.

`ordered_audio_files()` skips PDFs so sequential playback can walk audio items without treating documents as tracks.

## Admin project on disk (planned)

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

## Threading (later UI)

KDF, encryption, import, and bundle write/read run off the GUI thread. Models themselves are plain dataclasses.

## What is deferred

* Crypto engine, bundle bytes, Qt windows, audio, PDF, PyInstaller specs (placeholders only under `packaging/`).
