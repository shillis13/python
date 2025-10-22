#!/usr/bin/env sh
# Minimal wrapper for Variant B

DIR=$(CDPATH=; cd "$(dirname "$0")" && pwd)
exec python3 "$DIR/src/gdir.py" "$@"

# Example: cd "$(./wrapper.sh -g work)"
