#!/bin/sh
# Example wrapper showing how to cd using gdir Variant B
TARGET=$(gdir -g "$1") || exit $?
cd "$TARGET"
