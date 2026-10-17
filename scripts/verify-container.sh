#!/bin/bash
# Checks that a signalblast container or image on this machine is a published release: that its image is one that the
# release workflow of this repo signed, and that the container runs that image unmodified.
# Usage: scripts/verify-container.sh [--rebuild] [<container or image>] [<release tag, e.g. v1.2.3>]
# The container defaults to signalblast, its name in docker-compose.yaml.
# Without a release tag, the latest releases are searched for the one that the image belongs to.
# --rebuild also runs scripts/verify-release.sh for the release, which checks that it was built from the code in its git tag.
# Requires docker with buildx, jq, sha256sum and the GitHub CLI (gh), logged in with `gh auth login`.
set -euo pipefail

USAGE="usage: $0 [--rebuild] [<container or image, default signalblast>] [<release tag, e.g. v1.2.3>]"
REBUILD=false
while [[ ${1:-} == --* ]]; do
    case $1 in
        --rebuild) REBUILD=true ;;
        *) echo "unknown option $1, $USAGE" >&2; exit 1 ;;
    esac
    shift
done
TARGET=${1:-signalblast}
TAG=${2:-}
GITHUB_REPO=Gara-Dorta/signalblast
IMAGE=eradorta/signalblast
# How many releases are searched for the image when no release tag is given
SEARCH_LIMIT=20
SCRIPTS_DIR=$(dirname "$(realpath "$0")")

# The tools are checked up front, so that a missing one is reported before anything is downloaded
errors=()
for tool in docker jq sha256sum gh; do
    if ! command -v "$tool" > /dev/null; then
        errors+=("$tool is not installed")
    fi
done
if command -v docker > /dev/null; then
    if ! docker buildx version > /dev/null 2>&1; then
        errors+=("docker buildx is not installed")
    elif ! docker info > /dev/null 2>&1; then
        errors+=("docker is not running, or the user can't access it")
    fi
fi
if command -v gh > /dev/null; then
    if ! gh attestation --help > /dev/null 2>&1; then
        errors+=("gh is too old, it has no attestation command, install gh 2.49 or newer")
    elif ! gh auth status > /dev/null 2>&1; then
        errors+=("gh is not logged in, run gh auth login")
    fi
fi
if [ ${#errors[@]} -ne 0 ]; then
    printf 'Error: %s\n' "${errors[@]}" >&2
    exit 1
fi

WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

failed=0
report() {
    # report <result> <text>, aligned so that the texts form a column, the same as scripts/verify-release.sh
    printf '%-19s%s\n' "$1" "$2"
}

fail() {
    # fail <result> <text> [<detail>...]
    local detail
    report "$1" "$2"
    shift 2
    for detail in "$@"; do
        report "" "$detail"
    done
    failed=1
}

docker_tag() {
    # docker_tag <release tag>, the same conversion as the release workflow
    local version=${1#v}
    echo "${version//+/-}"
}

sha256() {
    # sha256 <file>, as a digest
    echo "sha256:$(sha256sum < "$1" | cut -d ' ' -f 1)"
}

download() {
    # download <image reference> <file>, fails if it isn't published.
    # Any other error, like the Docker Hub rate limit, stops the script, as it could hide the release that matches
    if ! docker buildx imagetools inspect --raw "$1" > "$2" 2> "$WORK_DIR/error.txt"; then
        if grep -q ': not found' "$WORK_DIR/error.txt"; then
            return 1
        fi
        cat "$WORK_DIR/error.txt" >&2
        exit 1
    fi
}

matches_release() {
    # matches_release <release tag>, succeeds if the local image is the one published for the release,
    # and sets INDEX_DIGEST to the digest of the published image index.
    # Depending on the docker image store, the local image id is the digest of the index, of the manifest for the platform,
    # or of that manifest's config. The digests are computed from what is downloaded, so the registry can't swap any of them.
    local index="$WORK_DIR/index.json" manifest="$WORK_DIR/manifest.json" manifest_digest
    download "${IMAGE}:$(docker_tag "$1")" "$index" || return 1
    INDEX_DIGEST=$(sha256 "$index")
    [ "$IMAGE_ID" = "$INDEX_DIGEST" ] && return 0

    manifest_digest=$(jq -r --arg os "${PLATFORM%/*}" --arg arch "${PLATFORM#*/}" \
        '[.manifests[]? | select(.platform.os == $os and .platform.architecture == $arch)][0].digest // empty' "$index")
    [ -n "$manifest_digest" ] || return 1
    [ "$IMAGE_ID" = "$manifest_digest" ] && return 0

    # Docker Hub limits the downloads, so if docker knows what the image was pulled by,
    # the manifest is only downloaded for that release
    if [ -n "$PULLED_DIGESTS" ] && ! grep -qxF -e "$INDEX_DIGEST" -e "$manifest_digest" <<< "$PULLED_DIGESTS"; then
        return 1
    fi
    download "${IMAGE}@${manifest_digest}" "$manifest" || return 1
    [ "$(sha256 "$manifest")" = "$manifest_digest" ] || return 1
    [ "$IMAGE_ID" = "$(jq -r '.config.digest' "$manifest")" ]
}

finish() {
    if [ "$failed" -ne 0 ]; then
        echo "The ${KIND} could not be verified"
        exit 1
    fi
}

# A running container keeps its image even if the tag was pulled again since, so the image is taken from the container
if docker container inspect "$TARGET" > "$WORK_DIR/container.json" 2> /dev/null; then
    KIND=container
    IMAGE_ID=$(jq -r '.[0].Image' "$WORK_DIR/container.json")
elif docker image inspect "$TARGET" > /dev/null 2>&1; then
    KIND=image
    IMAGE_ID=$(docker image inspect --format '{{.Id}}' "$TARGET")
else
    echo "Error: there is no container or image called ${TARGET}" >&2
    exit 1
fi
docker image inspect "$IMAGE_ID" | jq '.[0]' > "$WORK_DIR/image.json"
PLATFORM=$(jq -r '"\(.Os)/\(.Architecture)"' "$WORK_DIR/image.json")
# Empty if the image wasn't pulled from Docker Hub, e.g. if it was copied with docker save and docker load
PULLED_DIGESTS=$(jq -r --arg image "$IMAGE" \
    '.RepoDigests[]? | select(startswith($image + "@") or startswith("docker.io/" + $image + "@")) | sub("^.*@"; "")' \
    "$WORK_DIR/image.json")

if [ -n "$TAG" ]; then
    if ! matches_release "$TAG"; then
        fail "IMAGE DIFFERS" "${KIND} ${TARGET} is not the ${PLATFORM} image of ${IMAGE}:$(docker_tag "$TAG")" \
            "local image: ${IMAGE_ID}"
        finish
    fi
else
    echo "Searching the latest ${SEARCH_LIMIT} releases for the image of ${KIND} ${TARGET}"
    # Listed first, so that an error listing them isn't taken as no release matching
    releases=$(gh release list --repo "$GITHUB_REPO" --exclude-drafts --limit "$SEARCH_LIMIT" --json tagName --jq '.[].tagName')
    found=false
    while read -r TAG; do
        if matches_release "$TAG"; then
            found=true
            break
        fi
    done <<< "$releases"
    if ! $found; then
        fail "IMAGE DIFFERS" "${KIND} ${TARGET} is not the ${PLATFORM} image of any of the latest ${SEARCH_LIMIT} releases" \
            "local image: ${IMAGE_ID}"
        finish
    fi
fi
DOCKER_TAG=$(docker_tag "$TAG")
report "IMAGE MATCHES" "${KIND} ${TARGET} is ${IMAGE}:${DOCKER_TAG} for ${PLATFORM}"

# The signature is what ties the image to the release, the tag on Docker Hub only says where to find it
if output=$(gh attestation verify "oci://${IMAGE}@${INDEX_DIGEST}" \
    --repo "$GITHUB_REPO" \
    --signer-workflow "${GITHUB_REPO}/.github/workflows/publish-pypi.yml" \
    --source-ref "refs/tags/${TAG}" 2>&1); then
    report "SIGNATURE VALID" "Docker ${IMAGE}:${DOCKER_TAG}, signed by publish-pypi.yml at refs/tags/${TAG}"
else
    mapfile -t lines < <(grep -v '^$' <<< "$output")
    fail "SIGNATURE INVALID" "Docker ${IMAGE}:${DOCKER_TAG}" "${lines[@]}"
fi

if [ "$KIND" = container ]; then
    CONTAINER="$WORK_DIR/container.json"
    LOCAL_IMAGE="$WORK_DIR/image.json"

    # The image could be started with another command, which could run code from a mount or from an environment variable
    expected=$(jq -c '{command: ((.Config.Entrypoint // []) + (.Config.Cmd // [])), healthcheck: .Config.Healthcheck.Test}' \
        "$LOCAL_IMAGE")
    actual=$(jq -c '.[0] | {command: ([.Path] + .Args), healthcheck: .Config.Healthcheck.Test}' "$CONTAINER")
    differences=()
    for field in command healthcheck; do
        in_image=$(jq -c ".${field}" <<< "$expected")
        in_container=$(jq -c ".${field}" <<< "$actual")
        if [ "$in_image" != "$in_container" ]; then
            differences+=("${field} of the image:     ${in_image}" "${field} of the container: ${in_container}")
        fi
    done
    if [ ${#differences[@]} -eq 0 ]; then
        report "COMMAND MATCHES" "the container runs the command and health check of the image"
    else
        fail "COMMAND DIFFERS" "the container doesn't run the command and health check of the image" "${differences[@]}"
    fi

    # Only the settings in docker-compose.yaml can be added, others like PYTHONPATH could load other code.
    # Only the names are shown, as the values can be secrets
    mapfile -t unexpected < <(jq -r --slurpfile image "$LOCAL_IMAGE" '.[0].Config.Env[]
        | select(. as $var | $image[0].Config.Env | index([$var]) | not)
        | select(test("^(SIGNALBLAST_[A-Z_]+|TZ)=") | not)
        | sub("=.*"; "")' "$CONTAINER")
    if [ ${#unexpected[@]} -eq 0 ]; then
        report "ENV MATCHES" "the container only adds SIGNALBLAST_* and TZ variables to the image"
    else
        fail "ENV DIFFERS" "the container sets variables that the image doesn't" "${unexpected[@]}"
    fi

    # Only the data dir and /tmp can be mounted, a mount anywhere else could hide the files of the image
    DATA_DIR=$(jq -r '.Config.Env[] | select(startswith("SIGNALBLAST_DATA_DIR=")) | sub("^[^=]*="; "")' "$LOCAL_IMAGE")
    mapfile -t mount_points < <(jq -r '.[0] | ((.Mounts // [])[].Destination),(.HostConfig.Tmpfs // {} | keys[])' "$CONTAINER")
    unexpected=()
    for mount_point in "${mount_points[@]}"; do
        if [[ $mount_point != "$DATA_DIR" && $mount_point != "$DATA_DIR"/* && $mount_point != /tmp && $mount_point != /tmp/* ]]
        then
            unexpected+=("$mount_point")
        fi
    done
    if [ ${#unexpected[@]} -eq 0 ]; then
        report "MOUNTS MATCH" "the container only mounts ${DATA_DIR} and /tmp"
    else
        fail "MOUNTS DIFFER" "the container mounts other paths than ${DATA_DIR} and /tmp" "${unexpected[@]}"
    fi

    # Only /tmp can change, besides the directories that docker creates to mount on
    allowed_change() {
        local path=$1 mount_point
        [[ $path == /tmp || $path == /tmp/* ]] && return 0
        for mount_point in "${mount_points[@]}"; do
            [[ $mount_point == "$path" || $mount_point == "$path"/* ]] && return 0
        done
        return 1
    }
    changes=()
    while read -r kind path; do
        if ! allowed_change "$path"; then
            case $kind in
                A) changes+=("added:   $path") ;;
                C) changes+=("changed: $path") ;;
                D) changes+=("deleted: $path") ;;
            esac
        fi
    done < <(docker container diff "$TARGET")
    if [ ${#changes[@]} -eq 0 ]; then
        report "FILES MATCH" "the files of the container are those of the image, other than /tmp"
    else
        fail "FILES DIFFER" "files of the container changed since it started" "${changes[@]}"
    fi
fi

finish

if $REBUILD; then
    echo "Rebuilding ${TAG} with scripts/verify-release.sh"
    "${SCRIPTS_DIR}/verify-release.sh" "$TAG"
else
    echo "The ${KIND} is the signed release ${TAG}"
    echo "Add --rebuild to also check that the release was built from the code in its git tag"
fi
