# Audio Bundle (offline)

Desktop toolkit for distributing encrypted audio lessons and PDFs as a single `.audiobundle` file. Everything runs locally. There is no cloud, server, account system, or network requirement.

This repository is being built in milestones. **Milestones 1–8 are implemented**: core crypto/bundle format, Admin and Client UIs, full audio/PDF viewing, and PyInstaller specs.

## Status

| Milestone | Scope | Status |
| --- | --- | --- |
| 1 | Core models (`Project`, `Block`, `MediaItem`, `BundleManifest`) | Implemented |
| 2 | Crypto engine | Implemented |
| 3 | Bundle reader/writer | Implemented |
| 4 | Admin UI | Implemented |
| 5 | Client UI | Implemented |
| 6 | Audio player | Implemented |
| 7 | PDF viewer | Implemented |
| 8 | PyInstaller packaging | Implemented |

Design documents:

* [Architecture](docs/ARCHITECTURE.md)
* [Bundle format](docs/BUNDLE_FORMAT.md)
* [Security](docs/SECURITY.md)

## Requirements

* Python 3.12+

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

PySide6 is included so the Admin and Client applications can run offline on the desktop.

## Tests

```bash
pytest
```

## How to run

### Run the Admin application

```bash
audio-bundle-admin
```

1. **New project** — choose a parent folder and course name. The app creates `project.json`, `blocks/`, and `output/`.
2. Add blocks, then **Add files** to import MP3/WAV/M4A/AAC or PDF. Drag the ☰ rows to set playback/display order.
3. **Save** writes `project.json` (never passwords).
4. **Generate Bundle** asks for a main password and one password per block, then encrypts a `.audiobundle` on a background thread.

Opening a bundle: run `audio-bundle-client` (Milestone 5). The sample editable project lives at `samples/admin_project/project.json`.

### Run the Client application

```bash
audio-bundle-client
```

1. Choose a `.audiobundle` and enter the **main password**.
2. The course title and locked blocks appear. Unlock a block with its password.
3. The content viewer lists files in the administrator’s order. Audio includes play/pause/stop, next/previous, ±10s seek, a seek bar, volume/mute, and speed from 0.5x–2x. When a track ends, the next **audio** item starts (PDFs are skipped). PDFs open in an embedded viewer with page navigation, fit page/width, zoom, scroll, and text search when Qt PDF supports it.
4. Closing the bundle deletes the private temporary decrypt folder.

A sample bundle is at `samples/Sample_Course.audiobundle` (passwords in `samples/admin_project/README.md`).

### Encryption (high level)

Main and block passwords derive key-encryption keys with Argon2id. Random AES-256-GCM keys encrypt manifests and file bytes. See [docs/SECURITY.md](docs/SECURITY.md).

### Standalone executables

```bash
pip install -e ".[packaging]"
bash packaging/build.sh
```

See [packaging/README.md](packaging/README.md). Outputs: `dist/AudioBundleAdmin` and `dist/AudioBundleClient`.

## License

Internal use.
