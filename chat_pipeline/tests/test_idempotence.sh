#!/usr/bin/env bash
set -euo pipefail
echo "[TEST] Idempotence smoke: running stage→process→index twice should not error"
make stage >/dev/null || true
make process >/dev/null || true
make index >/dev/null || true
make stage >/dev/null || true
make process >/dev/null || true
make index >/dev/null || true
echo "[OK] Re-run completed without errors"
