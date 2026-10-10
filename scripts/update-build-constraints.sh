#!/bin/bash
# Updates build-constraints.txt, the pinned build backend used to build the package and the image.
# Usage:
#   scripts/update-build-constraints.sh              upgrades all the packages to their latest versions
#   scripts/update-build-constraints.sh hatchling    only upgrades the given packages
set -euo pipefail

cd "$(dirname "$(dirname "$(realpath "$0")")")"

if [ $# -eq 0 ]; then
    set -- --upgrade
else
    set -- "${@/#/--upgrade-package=}"
fi

# The packages are build-system.requires in pyproject.toml
uv run --no-project python -c \
    'import tomllib; print(*tomllib.load(open("pyproject.toml", "rb"))["build-system"]["requires"], sep="\n")' \
    | uv pip compile - \
        --generate-hashes \
        --universal \
        --python-version 3.14 \
        --quiet \
        --custom-compile-command "scripts/update-build-constraints.sh" \
        "$@" \
        --output-file build-constraints.txt

git --no-pager diff --stat -- build-constraints.txt
