#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "Running Volt interpreter test suite..."
python3 -m unittest discover -s tests -v

echo
echo "All tests passed."
