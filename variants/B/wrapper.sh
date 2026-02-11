#!/usr/bin/env sh
# Example wrapper for gdirB using flag interface

gdirB() {
  python -m variants.B.src.gdirb "$@"
}

cdb() {
  target=$(gdirB -g "$1") || return $?
  cd "$target"
}
