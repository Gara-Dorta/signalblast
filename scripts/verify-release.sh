#!/bin/bash
# Rebuilds a release from its git tag and checks that it is identical to what was published on PyPI and Docker Hub.
# Usage: scripts/verify-release.sh v1.2.3
# Set PLATFORMS to check fewer image platforms, e.g. PLATFORMS=linux/amd64, building other platforms needs QEMU.
# Requires git, uv, docker with buildx, curl and jq.
set -euo pipefail

TAG=${1:?usage: $0 <release tag, e.g. v1.2.3>}
export PLATFORMS=${PLATFORMS:-linux/amd64,linux/arm64}
# Overridable to test the script against a local repo and registry
REPO_URL=${REPO_URL:-https://github.com/Gara-Dorta/signalblast}
IMAGE=${IMAGE:-eradorta/signalblast}

# Same version and tag conversion as the release workflow
VERSION="${TAG#v}"
DOCKER_TAG="${VERSION//+/-}"

WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

failed=0
check() {
    # check <name> <published hash> <rebuilt hash>
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

if [ ! -f "$WORK_DIR/src/scripts/build-reproducible.sh" ]; then
    echo "${TAG} predates reproducible builds, it can't be verified" >&2
    exit 1
fi

# Built with the script from the tag, so that it is built the same way as the release was
echo "Building the release for ${PLATFORMS}"
"$WORK_DIR/src/scripts/build-reproducible.sh" "$WORK_DIR/out"
HASHES="$WORK_DIR/out/hashes.txt"

curl -fsSL "https://pypi.org/pypi/signalblast/${VERSION}/json" \
    | jq -r '.urls[] | "\(.filename) \(.digests.sha256)"' > "$WORK_DIR/pypi.txt"
while read -r filename published; do
    rebuilt=$(awk -v f="$filename" '$2 == f {print $1}' "$HASHES")
    check "PyPI   ${filename}" "$published" "${rebuilt:-<not rebuilt>}"
done < "$WORK_DIR/pypi.txt"

# Compared per platform, the published image index also has the provenance attestations so its digest differs
docker buildx imagetools inspect --raw "${IMAGE}:${DOCKER_TAG}" \
    | jq -r '.manifests[] | select(.platform.os != "unknown") | "\(.platform.os)/\(.platform.architecture) \(.digest)"' \
    > "$WORK_DIR/published.txt"
for platform in ${PLATFORMS//,/ }; do
    published=$(awk -v p="$platform" '$1 == p {print $2}' "$WORK_DIR/published.txt")
    rebuilt=$(awk -v p="$platform" '$2 == "image" && $3 == p {print $1}' "$HASHES")
    check "Docker ${IMAGE}:${DOCKER_TAG} ${platform}" "${published:-<not published>}" "${rebuilt:-<not rebuilt>}"
done

if [ "$failed" -ne 0 ]; then
    echo "The rebuilt release differs from the published one"
    exit 1
fi
echo "The release is reproducible"
