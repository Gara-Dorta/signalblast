#!/bin/bash
# Rebuilds a release from its git tag and checks that it is identical to what was published on PyPI and Docker Hub,
# and that the published files were signed by the release workflow of this repo.
# Usage: scripts/verify-release.sh [--signatures-only] v1.2.3
# --signatures-only only checks the signatures of the published files, which is much faster as nothing is rebuilt.
# Set PLATFORMS to check fewer image platforms, e.g. PLATFORMS=linux/amd64, building other platforms needs QEMU.
# Requires git, uv, docker with buildx, curl, jq and the GitHub CLI (gh), logged in with `gh auth login`.
set -euo pipefail

SIGNATURES_ONLY=false
if [ "${1:-}" = "--signatures-only" ]; then
    SIGNATURES_ONLY=true
    shift
fi
TAG=${1:?usage: $0 [--signatures-only] <release tag, e.g. v1.2.3>}
export PLATFORMS=${PLATFORMS:-linux/amd64,linux/arm64}
GITHUB_REPO=Gara-Dorta/signalblast
REPO_URL=https://github.com/${GITHUB_REPO}
IMAGE=eradorta/signalblast

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

signed() {
    # signed <name> <verification command...>
    local name=$1 output
    shift
    if output=$("$@" 2>&1); then
        echo "SIGNED    $name"
    else
        echo "UNSIGNED  $name"
        echo "$output"
        failed=1
    fi
}

finish() {
    # finish <message on success>
    if [ "$failed" -ne 0 ]; then
        echo "The release could not be verified"
        exit 1
    fi
    echo "$1"
    exit 0
}

if ! $SIGNATURES_ONLY; then
    echo "Cloning ${REPO_URL} at ${TAG}"
    git -c advice.detachedHead=false clone --quiet --depth 1 --branch "$TAG" "$REPO_URL" "$WORK_DIR/src"

    if [ ! -f "$WORK_DIR/src/scripts/build-reproducible.sh" ]; then
        echo "${TAG} predates reproducible builds, it can't be verified" >&2
        exit 1
    fi
fi

# What was published is fetched before the slow build, so that an unsigned image is reported straight away
curl -fsSL "https://pypi.org/pypi/signalblast/${VERSION}/json" \
    | jq -r '.urls[] | "\(.filename) \(.digests.sha256)"' > "$WORK_DIR/pypi.txt"

# The tag is resolved once, so that the image whose signature is checked is the one whose platforms are compared
DIGEST=$(docker buildx imagetools inspect "${IMAGE}:${DOCKER_TAG}" --format '{{.Manifest.Digest}}')
signed "Docker ${IMAGE}:${DOCKER_TAG}" gh attestation verify "oci://${IMAGE}@${DIGEST}" \
    --repo "$GITHUB_REPO" \
    --signer-workflow "${GITHUB_REPO}/.github/workflows/publish-pypi.yml" \
    --source-ref "refs/tags/${TAG}"

if $SIGNATURES_ONLY; then
    # The files on PyPI are checked, a full run also checks that they are identical to the rebuilt ones
    while read -r filename _; do
        signed "PyPI   ${filename}" uvx --quiet pypi-attestations verify pypi --repository "$REPO_URL" "pypi:${filename}"
    done < "$WORK_DIR/pypi.txt"
    finish "The release is signed"
fi

# Compared per platform, the published image index also has the provenance attestations so its digest differs
docker buildx imagetools inspect --raw "${IMAGE}@${DIGEST}" \
    | jq -r '.manifests[] | select(.platform.os != "unknown") | "\(.platform.os)/\(.platform.architecture) \(.digest)"' \
    > "$WORK_DIR/published.txt"

# Built with the script from the tag, so that it is built the same way as the release was
echo "Building the release for ${PLATFORMS}"
"$WORK_DIR/src/scripts/build-reproducible.sh" "$WORK_DIR/out"
HASHES="$WORK_DIR/out/hashes.txt"

while read -r filename published; do
    rebuilt=$(awk -v f="$filename" '$2 == f {print $1}' "$HASHES")
    check "PyPI   ${filename}" "$published" "${rebuilt:-<not rebuilt>}"
    if [ -n "$rebuilt" ]; then
        # Checks the signature published on PyPI against the rebuilt file
        signed "PyPI   ${filename}" uvx --quiet pypi-attestations verify pypi --repository "$REPO_URL" \
            "$WORK_DIR/out/dist/${filename}"
    fi
done < "$WORK_DIR/pypi.txt"

for platform in ${PLATFORMS//,/ }; do
    published=$(awk -v p="$platform" '$1 == p {print $2}' "$WORK_DIR/published.txt")
    rebuilt=$(awk -v p="$platform" '$2 == "image" && $3 == p {print $1}' "$HASHES")
    check "Docker ${IMAGE}:${DOCKER_TAG} ${platform}" "${published:-<not published>}" "${rebuilt:-<not rebuilt>}"
done

finish "The release is reproducible and signed"
