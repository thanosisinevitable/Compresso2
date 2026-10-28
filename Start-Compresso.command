#!/bin/bash
# Double-click in Finder, or run ./start from Terminal. Compatible with macOS Bash 3.2.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

compresso_fail() {
  printf '\n%s\n' "$1" >&2
  printf '\nInstall the prerequisites once, then open Start-Compresso.command again:\n' >&2
  printf '  brew install node python@3.12 ghostscript\n' >&2
  printf 'If Homebrew is missing, get it from https://brew.sh\n' >&2
  exit 1
}

compresso_on_exit() {
  compresso_status=$?
  if [ "$compresso_status" -ne 0 ] && [ -t 0 ]; then
    printf '\nCompresso could not start. The error is shown above.\nPress Return to close this window.\n'
    read -r _ || true
  fi
}
trap compresso_on_exit EXIT

command -v node >/dev/null 2>&1 || compresso_fail 'Node.js is missing.'
command -v npm >/dev/null 2>&1 || compresso_fail 'npm is missing.'
node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 22 ? 0 : 1)' \
  || compresso_fail 'Compresso needs Node.js 22 or newer.'

compresso_python=''
if [ -n "${COMPRESSO_PYTHON:-}" ]; then
  compresso_python="$COMPRESSO_PYTHON"
elif [ -x .venv/bin/python ]; then
  compresso_python="$PWD/.venv/bin/python"
else
  for compresso_candidate in python3.12 python3.13 python3.11 python3; do
    if command -v "$compresso_candidate" >/dev/null 2>&1 && \
      "$compresso_candidate" -c 'import sys; sys.exit(0 if (3,11) <= sys.version_info[:2] <= (3,13) else 1)' 2>/dev/null; then
      compresso_python="$(command -v "$compresso_candidate")"
      break
    fi
  done
fi
[ -n "$compresso_python" ] || compresso_fail 'Python 3.11-3.13 is missing. Python 3.12 is recommended.'
"$compresso_python" -c 'import sys; sys.exit(0 if (3,11) <= sys.version_info[:2] <= (3,13) else 1)' \
  || compresso_fail 'The selected Python is unavailable or unsupported. Install Python 3.12; recreate .venv if it was moved from another machine.'

if [ -z "${COMPRESSO_PYTHON:-}" ] && [ ! -x .venv/bin/python ]; then
  printf '\nPreparing Compresso for its first launch...\n'
  "$compresso_python" -m venv .venv
  compresso_python="$PWD/.venv/bin/python"
fi
export COMPRESSO_PYTHON="$compresso_python"

compresso_python_stamp='.compresso-python-requirements.sha256'
compresso_requirements_hash="$("$compresso_python" -c 'import hashlib,pathlib,sys; print(hashlib.sha256(sys.executable.encode()+sys.version.encode()+b"".join(pathlib.Path(p).read_bytes() for p in ["backend/requirements.txt","backend/requirements-dev.txt"])).hexdigest())')"
if [ ! -f "$compresso_python_stamp" ] || [ "$(cat "$compresso_python_stamp")" != "$compresso_requirements_hash" ] || ! "$compresso_python" -c 'import importlib.util,sys; sys.exit(0 if all(importlib.util.find_spec(m) for m in ["fastapi","uvicorn","PIL","imagehash","numpy","scipy","reportlab","skimage","pytest","httpx","PyInstaller","pypdf"]) else 1)'; then
  printf '\nInstalling Python dependencies (first launch or updated requirements)...\n'
  "$compresso_python" -m pip install -r backend/requirements-dev.txt
  printf '%s\n' "$compresso_requirements_hash" > "$compresso_python_stamp"
fi

compresso_lock_hash="$(node -e 'const fs=require("node:fs"),c=require("node:crypto"); console.log(c.createHash("sha256").update(fs.readFileSync("package-lock.json")).digest("hex"))')"
if [ ! -f node_modules/.compresso-lock.sha256 ] || [ "$(cat node_modules/.compresso-lock.sha256)" != "$compresso_lock_hash" ] || [ ! -f node_modules/electron/index.js ] || [ ! -f node_modules/vite/bin/vite.js ]; then
  printf '\nInstalling app dependencies (first launch or updated lockfile)...\n'
  npm ci
  printf '%s\n' "$compresso_lock_hash" > node_modules/.compresso-lock.sha256
fi

if ! command -v gs >/dev/null 2>&1; then
  printf '\nPDF processing needs Ghostscript: brew install ghostscript\nOther tools can still be used.\n'
fi
printf '\nStarting Compresso. Keep this window open; use Cmd+Q to quit the app.\n'
npm run dev
