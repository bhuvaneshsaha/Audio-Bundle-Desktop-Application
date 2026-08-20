#!/usr/bin/env bash
# Git Bash on Windows: ignore CR if the working tree still has CRLF.
(set -o igncr) 2>/dev/null && set -o igncr
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
else
  PYTHON=python
fi

"$PYTHON" -m pip install -e ".[packaging]"
"$PYTHON" -m PyInstaller --noconfirm --clean "$ROOT/packaging/admin.spec"
"$PYTHON" -m PyInstaller --noconfirm --clean "$ROOT/packaging/client.spec"
echo "Built dist/AudioBundleAdmin and dist/AudioBundleClient"
