#!/bin/sh
# Example wrapper to jump directories via gdir
set -e
cd "$(gdir go "$@")"
