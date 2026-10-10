#!/bin/bash
# Builds the wheel, the source dist and the image of the current commit, and writes their hashes to <out dir>/hashes.txt
# Usage: scripts/build-reproducible.sh <out dir>
# Set PLATFORMS to build fewer image platforms, e.g. PLATFORMS=linux/amd64, building other platforms needs QEMU.
# Used by the reproducibility workflow and scripts/verify-release.sh, so that both build the same way.
set -euo pipefail

mkdir -p "${1:?usage: $0 <out dir>}"
OUT_DIR=$(realpath "$1")
PLATFORMS=${PLATFORMS:-linux/amd64,linux/arm64}
cd "$(dirname "$(dirname "$(realpath "$0")")")"

# Use the commit time instead of the current time, buildx also reads it from the env
SOURCE_DATE_EPOCH=$(git log -1 --format=%ct)
export SOURCE_DATE_EPOCH
SIGNALBLAST_VERSION=$(uvx hatch version)

uv build --quiet --build-constraint build-constraints.txt --require-hashes --out-dir "$OUT_DIR/dist"

docker buildx build --quiet --no-cache \
    --platform "$PLATFORMS" \
    --build-arg SIGNALBLAST_VERSION="$SIGNALBLAST_VERSION" \
    --provenance=false \
    --output type=oci,dest="$OUT_DIR/image.tar",rewrite-timestamp=true \
    . > /dev/null

# "<sha256>  <file>" for the distributions and "<digest>  image <os>/<arch>" for each image platform
(cd "$OUT_DIR/dist" && sha256sum -- *) > "$OUT_DIR/hashes.txt"
top=$(tar -xOf "$OUT_DIR/image.tar" index.json | jq -c '.manifests[0]')
if [[ $(jq -r '.mediaType' <<< "$top") == *index* ]]; then
    index=$(jq -r '.digest' <<< "$top")
    tar -xOf "$OUT_DIR/image.tar" "blobs/sha256/${index#sha256:}" \
        | jq -r '.manifests[] | "\(.digest)  image \(.platform.os)/\(.platform.architecture)"'
else
    # A single platform build has no image index, just the image itself
    echo "$(jq -r '.digest' <<< "$top")  image $PLATFORMS"
fi >> "$OUT_DIR/hashes.txt"
