#!/bin/sh
# Usage: source this file to add gdircd helper
# Example: cd "$(gdir go proj)"

gdircd() {
    target="$(gdir go "$@")" || return $?
    cd "$target" || return $?
}
