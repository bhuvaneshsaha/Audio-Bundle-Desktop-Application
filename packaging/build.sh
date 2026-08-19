#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 -m pip install -e ".[packaging]"
pyinstaller --noconfirm --clean "$ROOT/packaging/admin.spec"
pyinstaller --noconfirm --clean "$ROOT/packaging/client.spec"
echo "Built dist/AudioBundleAdmin and dist/AudioBundleClient"
