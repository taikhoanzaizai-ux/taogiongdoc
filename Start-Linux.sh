#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export QUAN_VOICE_DATA="${QUAN_VOICE_DATA:-$PWD/data}"
mkdir -p "$QUAN_VOICE_DATA/temp" "$QUAN_VOICE_DATA/cache/pip"
export TMPDIR="$QUAN_VOICE_DATA/temp" PIP_CACHE_DIR="$QUAN_VOICE_DATA/cache/pip"
if [ ! -x .app-env/bin/python ]; then
  python3 -m venv .app-env
fi
if [ ! -f .app-env/installed.ok ]; then
  .app-env/bin/python -m pip install -r desktop/requirements.txt
  touch .app-env/installed.ok
fi
command -v ffmpeg >/dev/null || { echo 'Cài ffmpeg trước khi chạy.'; exit 1; }
exec .app-env/bin/python desktop/server.py
