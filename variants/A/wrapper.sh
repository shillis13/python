#!/bin/sh
# Example wrapper showing how to cd using gdir Variant A
TARGET=$(gdir go "$1") || exit $?
cd "$TARGET"
