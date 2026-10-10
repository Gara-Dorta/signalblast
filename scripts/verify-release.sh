#!/bin/bash
# Rebuilds a release from its git tag and checks that it is identical to what was published on PyPI and Docker Hub.
# Usage: scripts/verify-release.sh v1.2.3
# Set PLATFORMS to check fewer image platforms, e.g. PLATFORMS=linux/amd64, building other platforms needs QEMU.
# Requires git, uv, docker with buildx, curl and jq.
set -euo pipefail

TAG=${1:?usage: $0 <release tag, e.g. v1.2.3>}
PLATFORMS=${PLATFORMS:-linux/amd64,linux/arm64}
REPO_URL=${REPO_URL:-https://github.com/Gara-Dorta/signalblast}
IMAGE=${IMAGE:-eradorta/signalblast}

# Same version and tag conversion as the release workflow
VERSION="${TAG#v}"
DOCKER_TAG="${VERSION//+/-}"

WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

failed=0
check() {
    # check <name> <expected hash> <rebuilt hash>
    if [ "$2" = "$3" ]; then
        echo "OK        $1"
    else
        echo "MISMATCH  $1"
        echo "          published: $2"
        echo "          rebuilt:   $3"
        failed=1
    fi
}

echo "Cloning ${REPO_URL} at ${TAG}"
git -c advice.detachedHead=false clone --quiet --depth 1 --branch "$TAG" "$REPO_URL" "$WORK_DIR/src"
cd "$WORK_DIR/src"

if [ ! -f build-constraints.txt ]; then
    echo "${TAG} predates reproducible builds, it can't be verified" >&2
    exit 1
fi

SOURCE_DATE_EPOCH=$(git log -1 --format=%ct)
export SOURCE_DATE_EPOCH

echo "Building the package distributions"
uv build --quiet --build-constraint build-constraints.txt --require-hashes --out-dir "$WORK_DIR/dist"

curl -fsSL "https://pypi.org/pypi/signalblast/${VERSION}/json" \
    | jq -r '.urls[] | "\(.filename) \(.digests.sha256)"' > "$WORK_DIR/pypi.txt"
while read -r filename published; do
    rebuilt=$(sha256sum "$WORK_DIR/dist/$filename" 2>/dev/null | cut -d' ' -f1 || true)
    check "PyPI   ${filename}" "$published" "${rebuilt:-<not rebuilt>}"
done < "$WORK_DIR/pypi.txt"

echo "Building the image for ${PLATFORMS}"
docker buildx build --quiet --no-cache \
    --platform "$PLATFORMS" \
    --build-arg SIGNALBLAST_VERSION="$VERSION" \
    --provenance=false \
    --output type=oci,dest="$WORK_DIR/image.tar",rewrite-timestamp=true \
    . > /dev/null

# Compare per platform, the published index also contains the provenance attestations so its digest differs
digests() {
    # Prints "<os>/<arch> <digest>" for each platform image in an image index read from stdin
    jq -r '.manifests[] | select(.platform.os != "unknown") | "\(.platform.os)/\(.platform.architecture) \(.digest)"'
}
docker buildx imagetools inspect --raw "${IMAGE}:${DOCKER_TAG}" | digests > "$WORK_DIR/published.txt"
top=$(tar -xOf "$WORK_DIR/image.tar" index.json | jq -c '.manifests[0]')
if [[ $(jq -r '.mediaType' <<< "$top") == *index* ]]; then
    digest=$(jq -r '.digest' <<< "$top")
    tar -xOf "$WORK_DIR/image.tar" "blobs/sha256/${digest#sha256:}" | digests > "$WORK_DIR/rebuilt.txt"
else
    # A single platform build has no image index, just the image itself
    echo "$PLATFORMS $(jq -r '.digest' <<< "$top")" > "$WORK_DIR/rebuilt.txt"
fi

for platform in ${PLATFORMS//,/ }; do
    published=$(awk -v p="$platform" '$1 == p {print $2}' "$WORK_DIR/published.txt")
    rebuilt=$(awk -v p="$platform" '$1 == p {print $2}' "$WORK_DIR/rebuilt.txt")
    check "Docker ${IMAGE}:${DOCKER_TAG} ${platform}" "${published:-<not published>}" "${rebuilt:-<not rebuilt>}"
done

if [ "$failed" -ne 0 ]; then
    echo "The rebuilt release differs from the published one"
    exit 1
fi
echo "The release is reproducible"
