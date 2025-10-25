#!/usr/bin/env sh
# Example wrapper for gdirA
# usage: source this file, then call cda KEY to jump

gdirA() {
  python -m variants.A.src.gdir "$@"
}

cda() {
  target=$(gdirA go "$1") || return $?
  cd "$target"
}
