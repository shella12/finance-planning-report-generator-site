#!/usr/bin/env bash
# Sets the Homebrew dylib path so WeasyPrint can find pango/cairo on macOS,
# then launches the Flask dev server on http://127.0.0.1:5050.
set -e
cd "$(dirname "$0")"
export DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib:${DYLD_FALLBACK_LIBRARY_PATH:-}"
exec python3 app.py
