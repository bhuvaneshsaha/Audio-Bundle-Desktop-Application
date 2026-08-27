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
* [Authentication](docs/AUTHENTICATION.md)
* [Block authentication (Windows vs password)](docs/BLOCK_AUTHENTICATION_SECURITY.md)

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
2. Add **day folders** (Day 1, Day 2, … at one level; they can be renamed) and **blocks** inside the selected day. Folders are organization only; sequence is per day. Then **Add files** to import MP3/WAV/M4A/AAC or PDF. Drag the ☰ file rows to set playback/display order.
3. Choose **one unlock method for all blocks**: custom password, Windows authentication, or no password. Custom passwords stay in session memory (Show password is available). Optional Windows allow-list: `DOMAIN\user`, `user@domain`, or later `group:DOMAIN\Group`.
4. Course options: auto-play, **one unlocked block at a time**, **open blocks in order within each folder**.
5. **Save** writes `project.json` (never passwords). **Generate Bundle** asks for the main password and writes the `.audiobundle` plus a separate `*-passwords.txt` you can share independently.

Opening a bundle: run `audio-bundle-client`. The sample editable project lives at `samples/admin_project/project.json`.

### Run the Client application

```bash
audio-bundle-client
```

1. **Windows sign-in** (required): user name and password, or Windows Hello / PIN / fingerprint for the account already logged on to this PC. Shared machines can have more than one user — type credentials to sign in as someone else. Use `DOMAIN\user` or `user@domain` after Active Directory join.
2. Choose a `.audiobundle` and enter the **main password**.
3. Unlock blocks with the **course-wide** method the Admin chose (Windows again, custom password, or none). Folders can be opened in any order; block sequence applies only inside the same folder. Press **F1** for keyboard shortcuts. If single-active is enabled, opening another block locks the previous one.
4. Select a file to decrypt and view it. Closing the bundle deletes the private temporary decrypt folder.

A sample bundle is at `samples/Sample_Course.audiobundle` (passwords in `samples/admin_project/README.md`).

### Encryption (high level)

Main and block passwords derive key-encryption keys with Argon2id. Random AES-256-GCM keys encrypt manifests and file bytes. See [docs/SECURITY.md](docs/SECURITY.md).

### Standalone executables

Windows PowerShell:

```powershell
pip install -e ".[packaging]"
.\packaging\build.ps1
```

macOS/Linux:

```bash
pip install -e ".[packaging]"
bash packaging/build.sh
```

See [packaging/README.md](packaging/README.md). Outputs: `dist/AudioBundleAdmin` and `dist/AudioBundleClient` (`.exe` on Windows).

## License

Internal use.
