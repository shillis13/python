#!/bin/bash
ALL_PACKAGES=("ai_utils" "archive_utils" "file_utils")
packages_to_install=("${ALL_PACKAGES[@]}")
echo "Array has ${#packages_to_install[@]} items"
for pkg in "${packages_to_install[@]}"; do
    echo "Package: $pkg"
done
