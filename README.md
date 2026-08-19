# Audio Bundle (offline)

Desktop toolkit for distributing encrypted audio lessons and PDFs as a single `.audiobundle` file. Everything runs locally. There is no cloud, server, account system, or network requirement.

This repository is being built in milestones. **Milestone 3 (current)** implements the versioned `.audiobundle` reader/writer on top of the crypto engine. Admin/Client UIs come later.

## Status

| Milestone | Scope | Status |
| --- | --- | --- |
| 1 | Core models (`Project`, `Block`, `MediaItem`, `BundleManifest`) | Implemented |
| 2 | Crypto engine | Implemented |
| 3 | Bundle reader/writer | Implemented |
| 4 | Admin UI | Not started |
| 5 | Client UI | Not started |
| 6 | Audio player | Not started |
| 7 | PDF viewer | Not started |
| 8 | PyInstaller packaging | Not started |

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

## Tests

```bash
pytest
```

## How this will work (once later milestones land)

### Run the Admin application

```bash
audio-bundle-admin
```

Create a project, add blocks, import audio/PDF files, drag to reorder, then **Generate Bundle**. Passwords are entered at generation time and are never written to the project file.

### Run the Client application

```bash
audio-bundle-client
```

Open a `.audiobundle`, enter the main password, then unlock individual blocks with their passwords.

### Create a project / generate a bundle / open a bundle

Not available until Milestones 3–5. The sample editable project lives at `samples/admin_project/project.json`.

### Encryption (high level)

Main and block passwords derive key-encryption keys with Argon2id. Random AES-256-GCM keys encrypt manifests and file bytes. See [docs/SECURITY.md](docs/SECURITY.md).

### Standalone executables

PyInstaller specs will live under `packaging/` in Milestone 8.

## License

Internal use.
