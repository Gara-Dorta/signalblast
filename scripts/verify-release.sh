#!/bin/bash
# Rebuilds a release from its git tag and checks that it is identical to what was published on PyPI and Docker Hub,
# that the tag was signed by one of the keys in .github/allowed_signers,
# and that the published files were signed by the release workflow of this repo.
# Usage: scripts/verify-release.sh [--signatures-only] [--all-platforms] v1.2.3
# --signatures-only only checks the signatures of the tag and the published files, which is much faster as nothing is rebuilt.
# --all-platforms rebuilds the image for all the platforms it was published for, instead of only the one of this machine.
#   Building for other platforms needs QEMU.
# Requires git, uv, docker with buildx, curl, jq and the GitHub CLI (gh), logged in with `gh auth login`.
set -euo pipefail

USAGE="usage: $0 [--signatures-only] [--all-platforms] <release tag, e.g. v1.2.3>"
SIGNATURES_ONLY=false
ALL_PLATFORMS=false
while [[ ${1:-} == --* ]]; do
    case $1 in
        --signatures-only) SIGNATURES_ONLY=true ;;
        --all-platforms) ALL_PLATFORMS=true ;;
        *) echo "unknown option $1, $USAGE" >&2; exit 1 ;;
    esac
    shift
done
TAG=${1:?$USAGE}

# shellcheck source=scripts/verify-common.sh
source "$(dirname "$(realpath "$0")")/verify-common.sh"

requirements=(git ssh-keygen uv uvx curl jq docker gh docker-buildx gh-attestation allowed-signers)
if ! $SIGNATURES_ONLY; then
    requirements+=(sha256sum tar docker-running)
fi
check_requirements "${requirements[@]}"

VERSION="${TAG#v}"
DOCKER_TAG=$(docker_tag "$TAG")

WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

check() {
    # check <name> <published hash> <rebuilt hash>
    if [ "$2" = "$3" ]; then
        report "REBUILD MATCHES" "$1"
    else
        fail "REBUILD DIFFERS" "$1" "published: $2" "rebuilt:   $3"
    fi
}

signed() {
    # signed <name> <signer> <verification command...>
    local name=$1 signer=$2 output
    shift 2
    if output=$("$@" 2>&1); then
        valid "$name" "$signer"
    else
        invalid "$name" "$output"
    fi
}

finish() {
    # finish <message on success>
    exit_if_failed release
    echo "$1"
    exit 0
}

echo "Fetching ${TAG} from ${REPO_URL}"
fetch_tag "$TAG" "$WORK_DIR/src"

if ! $SIGNATURES_ONLY && [ ! -f "$WORK_DIR/src/scripts/build-reproducible.sh" ]; then
    echo "${TAG} predates reproducible builds, it can't be verified" >&2
    exit 1
fi

verify_tag "$TAG" "$WORK_DIR/src"

# What was published is fetched before the slow build, so that an unsigned image is reported straight away
curl -fsSL "https://pypi.org/pypi/signalblast/${VERSION}/json" \
    | jq -r '.urls[] | "\(.filename) \(.digests.sha256)"' > "$WORK_DIR/pypi.txt"

# The tag is resolved once, so that the image whose signature is checked is the one whose platforms are compared
DIGEST=$(docker buildx imagetools inspect "${IMAGE}:${DOCKER_TAG}" --format '{{.Manifest.Digest}}')
verify_image_signature "$TAG" "oci://${IMAGE}@${DIGEST}"

if $SIGNATURES_ONLY; then
    # The files on PyPI are checked, a full run also checks that they are identical to the rebuilt ones
    while read -r filename _; do
        signed "PyPI   ${filename}" "$GITHUB_REPO" \
            uvx --quiet pypi-attestations verify pypi --repository "$REPO_URL" "pypi:${filename}"
    done < "$WORK_DIR/pypi.txt"
    finish "The release is signed"
fi

# Compared per platform, so that only some of them can be rebuilt
docker buildx imagetools inspect --raw "${IMAGE}@${DIGEST}" \
    | jq -r '.manifests[] | "\(.platform.os)/\(.platform.architecture) \(.digest)"' \
    > "$WORK_DIR/published.txt"
if $ALL_PLATFORMS; then
    PLATFORMS=$(cut -d ' ' -f 1 "$WORK_DIR/published.txt" | paste -sd , -)
else
    PLATFORMS=$(docker version --format '{{.Server.Os}}/{{.Server.Arch}}')
fi
export PLATFORMS

# Built with the script from the tag, so that it is built the same way as the release was
echo "Building the release for ${PLATFORMS}"
"$WORK_DIR/src/scripts/build-reproducible.sh" "$WORK_DIR/out"
HASHES="$WORK_DIR/out/hashes.txt"

while read -r filename published; do
    rebuilt=$(awk -v f="$filename" '$2 == f {print $1}' "$HASHES")
    check "PyPI   ${filename}" "$published" "${rebuilt:-<not rebuilt>}"
    if [ -n "$rebuilt" ]; then
        # Checks the signature published on PyPI against the rebuilt file
        signed "PyPI   ${filename}" "$GITHUB_REPO" \
            uvx --quiet pypi-attestations verify pypi --repository "$REPO_URL" "$WORK_DIR/out/dist/${filename}"
    fi
done < "$WORK_DIR/pypi.txt"

for platform in ${PLATFORMS//,/ }; do
    published=$(awk -v p="$platform" '$1 == p {print $2}' "$WORK_DIR/published.txt")
    rebuilt=$(awk -v p="$platform" '$2 == "image" && $3 == p {print $1}' "$HASHES")
    check "Docker ${IMAGE}:${DOCKER_TAG} ${platform}" "${published:-<not published>}" "${rebuilt:-<not rebuilt>}"
done

finish "The release is reproducible and signed"
