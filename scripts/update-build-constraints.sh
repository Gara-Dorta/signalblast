#!/bin/bash
# Updates build-constraints.txt, the pinned build backend used to build the package and the image.
# Usage:
#   scripts/update-build-constraints.sh              upgrades all the packages to their latest versions
#   scripts/update-build-constraints.sh hatchling    only upgrades the given packages
set -euo pipefail

REPO_DIR=$(dirname "$(dirname "$(realpath "$0")")")
cd "$REPO_DIR"

if [ $# -eq 0 ]; then
    upgrade=(--upgrade)
else
    upgrade=()
    for package in "$@"; do
        upgrade+=(--upgrade-package "$package")
    done
fi

# These must match build-system.requires in pyproject.toml
printf 'hatchling\nhatch-vcs\n' | uv pip compile - \
    --generate-hashes \
    --universal \
    --python-version 3.14 \
    --quiet \
    --custom-compile-command "scripts/update-build-constraints.sh" \
    "${upgrade[@]}" \
    --output-file build-constraints.txt

git --no-pager diff --stat -- build-constraints.txt
