# Packaging (Milestone 8)

Build offline standalone executables with PyInstaller. Do this on the target OS (Windows/macOS/Linux). The specs do not include network libraries beyond what PySide6/cryptography already ship.

## Prerequisites

```bash
pip install -e ".[packaging]"
```

## Build

```bash
bash packaging/build.sh
```

Or separately:

```bash
pyinstaller --noconfirm --clean packaging/admin.spec
pyinstaller --noconfirm --clean packaging/client.spec
```

Outputs (one-file, windowed):

* `dist/AudioBundleAdmin`
* `dist/AudioBundleClient`

On Windows the names gain `.exe`. Copy the executable to the user’s machine; no Python install is required.

`run_admin.py` and `run_client.py` are the analysis entry points so PyInstaller can see the real imports.
