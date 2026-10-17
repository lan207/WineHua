#!/usr/bin/env bash
# WineHua validates runtime identities and native contracts; VPP UI is excluded.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$ROOT/scripts/verify_runtime_migration.py" "$@"
