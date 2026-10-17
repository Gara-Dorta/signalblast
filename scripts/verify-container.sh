#!/bin/bash
# Checks that a signalblast container or image on this machine is a published release: that its image is one that the
# release workflow of this repo signed, and that the container runs that image unmodified.
# For a container, it also checks the signal-cli-rest-api container that signalblast talks to, as it decrypts every message:
# that it runs, unmodified, the image that the docker-compose.yaml of the release pins, and that the bot's Signal account
# has no linked devices. The containers can only add the variables and mounts of their services in that docker-compose.yaml.
# Usage: scripts/verify-container.sh [--rebuild] [<container or image>] [<release tag, e.g. v1.2.3>]
# The container defaults to signalblast, its name in docker-compose.yaml.
# Without a release tag, the latest releases are searched for the one that the image belongs to.
# --rebuild also runs scripts/verify-release.sh for the release, which checks that it was built from the code in its git tag.
# Asks signalblast for the address of signal-cli-rest-api, and signal-cli-rest-api for the devices of the account,
# inside their containers with docker exec.
# Requires git, ssh-keygen, docker with buildx and compose, jq, sha256sum and the GitHub CLI (gh), logged in with `gh auth login`.
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
SCRIPTS_DIR=$(dirname "$(realpath "$0")")
# How many releases are searched for the image when no release tag is given
SEARCH_LIMIT=20

# shellcheck source=scripts/verify-common.sh
source "${SCRIPTS_DIR}/verify-common.sh"

check_requirements git ssh-keygen docker jq sha256sum gh docker-buildx docker-compose docker-running gh-attestation

WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

sha256() {
    # sha256 <file>, as a digest
    echo "sha256:$(sha256sum < "$1" | cut -d ' ' -f 1)"
}

inspect_image() {
    # inspect_image <image> <file>
    docker image inspect --format '{{json .}}' "$1" > "$2"
}

env_var() {
    # env_var <inspect json> <name>, the value of an environment variable of an image or a container
    jq -r --arg prefix "$2=" '.Config.Env[] | select(startswith($prefix)) | ltrimstr($prefix)' "$1"
}

platform() {
    # platform <image inspect json>, e.g. linux/amd64
    jq -r '"\(.Os)/\(.Architecture)"' "$1"
}

download() {
    # download <image reference> <file>, fails if it isn't published.
    # Any other error, like the Docker Hub rate limit, stops the script, as it could hide the image that matches
    local error
    if ! error=$(docker buildx imagetools inspect --raw "$1" 2>&1 > "$2"); then
        if [[ $error == *': not found'* ]]; then
            return 1
        fi
        echo "$error" >&2
        exit 1
    fi
}

matches_image() {
    # matches_image <image inspect json> <repository> <:tag or @digest>, succeeds if the local image is the one published as
    # <repository><:tag or @digest>. The published image index is left in $WORK_DIR/index.json, and its digest in INDEX_DIGEST.
    # Depending on the docker image store, the local image id is the digest of the index, of the manifest for the platform,
    # or of that manifest's config. The digests are computed from what is downloaded, so the registry can't swap any of them.
    local image_json=$1 repository=$2 index="$WORK_DIR/index.json" manifest="$WORK_DIR/manifest.json"
    local id platform pulled_digests manifest_digest
    id=$(jq -r '.Id' "$image_json")
    platform=$(platform "$image_json")
    download "${repository}$3" "$index" || return 1
    INDEX_DIGEST=$(sha256 "$index")
    [ "$id" = "$INDEX_DIGEST" ] && return 0

    manifest_digest=$(jq -r --arg os "${platform%/*}" --arg arch "${platform#*/}" \
        '[.manifests[]? | select(.platform.os == $os and .platform.architecture == $arch)][0].digest // empty' "$index")
    [ -n "$manifest_digest" ] || return 1
    [ "$id" = "$manifest_digest" ] && return 0

    # Docker Hub limits the downloads, so if docker knows what the image was pulled by, the manifest is only downloaded
    # for that image. It doesn't know if the image wasn't pulled from Docker Hub, e.g. if it was copied with docker load
    pulled_digests=$(jq -r --arg repository "$repository" '.RepoDigests[]?
        | select(startswith($repository + "@") or startswith("docker.io/" + $repository + "@")) | sub("^.*@"; "")' \
        "$image_json")
    if [ -n "$pulled_digests" ] && ! grep -qxF -e "$INDEX_DIGEST" -e "$manifest_digest" <<< "$pulled_digests"; then
        return 1
    fi
    download "${repository}@${manifest_digest}" "$manifest" || return 1
    [ "$(sha256 "$manifest")" = "$manifest_digest" ] || return 1
    [ "$id" = "$(jq -r '.config.digest' "$manifest")" ]
}

compose_service() {
    # compose_service <service>, the image, the names of the variables and the mount points of a service of the
    # docker-compose.yaml of the release, as {image, environment, volumes, tmpfs}
    jq --arg service "$1" '.services[$service] | {
        image,
        environment: (.environment // {} | if type == "object" then keys else map(sub("=.*"; "")) end),
        volumes: [.volumes[]?.target],
        tmpfs: [.tmpfs[]? | sub(":.*"; "")]
    }' "$WORK_DIR/compose.json"
}

check_container() {
    # check_container <container> <container inspect json> <image inspect json> <compose service json>, checks that the
    # container runs its image unmodified, only adding the variables and mounts of its service in docker-compose.yaml
    local name=$1 container=$2 image=$3 service=$4
    local image_command container_command image_healthcheck container_healthcheck differences=() unexpected=()
    local mount_points=() mount_point changes=() kind path created

    # The image could be started with another command, which could run code from a mount or from an environment variable
    image_command=$(jq -c '(.Config.Entrypoint // []) + (.Config.Cmd // [])' "$image")
    container_command=$(jq -c '[.Path] + .Args' "$container")
    image_healthcheck=$(jq -c '.Config.Healthcheck.Test' "$image")
    container_healthcheck=$(jq -c '.Config.Healthcheck.Test' "$container")
    if [ "$image_command" != "$container_command" ]; then
        differences+=("command of the image:          ${image_command}" "command of the container:      ${container_command}")
    fi
    if [ "$image_healthcheck" != "$container_healthcheck" ]; then
        differences+=("health check of the image:     ${image_healthcheck}"
            "health check of the container: ${container_healthcheck}")
    fi
    if [ ${#differences[@]} -eq 0 ]; then
        report "COMMAND MATCHES" "${name} runs the command and health check of its image"
    else
        fail "COMMAND DIFFERS" "${name} doesn't run the command and health check of its image" "${differences[@]}"
    fi

    # Other variables, like PYTHONPATH, could load other code. Only the names are shown, as the values can be secrets
    mapfile -t unexpected < <(jq -r --slurpfile image "$image" --slurpfile service "$service" '.Config.Env[]
        | select(. as $var | $image[0].Config.Env | index([$var]) | not)
        | sub("=.*"; "")
        | select(. as $name | $service[0].environment | index([$name]) | not)' "$container")
    if [ ${#unexpected[@]} -eq 0 ]; then
        report "ENV MATCHES" "${name} only adds the variables of its service in docker-compose.yaml"
    else
        fail "ENV DIFFERS" "${name} sets variables that its image and docker-compose.yaml don't" "${unexpected[@]}"
    fi

    # A mount anywhere else could hide the files of the image. Where the service has a tmpfs only a tmpfs is allowed,
    # as other mounts could bring in files from the host. /tmp can be mounted too, as it can change anyway
    mapfile -t unexpected < <(jq -r --slurpfile service "$service" '
        def under($paths): . as $path | any($paths[]; $path == . or ($path | startswith(. + "/")));
        ([(.Mounts // [])[] | {type: .Type, path: .Destination}] + [.HostConfig.Tmpfs // {} | keys[] | {type: "tmpfs", path: .}])[]
        | select(((.path | under($service[0].volumes + ["/tmp"])) or (.type == "tmpfs" and (.path | under($service[0].tmpfs))))
            | not)
        | "\(.type) \(.path)"' "$container")
    if [ ${#unexpected[@]} -eq 0 ]; then
        report "MOUNTS MATCH" "${name} only mounts what its service in docker-compose.yaml does, and /tmp"
    else
        fail "MOUNTS DIFFER" "${name} mounts paths that docker-compose.yaml doesn't" "${unexpected[@]}"
    fi

    # Only /tmp can change, besides the directories that docker creates to mount on.
    # docker only sees the changes since the container was created, so its creation time is shown
    mapfile -t mount_points < <(jq -r '((.Mounts // [])[].Destination), (.HostConfig.Tmpfs // {} | keys[])' "$container")
    while read -r kind path; do
        if [[ $path == /tmp || $path == /tmp/* ]]; then
            continue
        fi
        for mount_point in "${mount_points[@]}"; do
            if [[ $mount_point == "$path" || $mount_point == "$path"/* ]]; then
                continue 2
            fi
        done
        case $kind in
            A) changes+=("added:   $path") ;;
            C) changes+=("changed: $path") ;;
            D) changes+=("deleted: $path") ;;
        esac
    done < <(docker container diff "$name")
    created=$(jq -r '.Created | sub("\\.[0-9]+"; "") | sub("T"; " ")' "$container")
    if [ ${#changes[@]} -eq 0 ]; then
        report "FILES MATCH" "no files of ${name} changed outside /tmp since it was created on ${created}"
    else
        fail "FILES DIFFER" "files of ${name} changed since it was created on ${created}" "${changes[@]}"
    fi
}

find_api_container() {
    # Finds the signal-cli-rest-api container that signalblast talks to, and sets API_CONTAINER to its name.
    # The address is asked from signalblast, inside its container that was just checked, so that it is the address that
    # it uses, also when SIGNALBLAST_SIGNAL_SERVICE isn't set. -B so that no bytecode is written, which would change its files
    local python address host port ids=() matches=() api_port
    python="$(dirname "$(jq -r '.Config.Entrypoint[0]' "$WORK_DIR/image.json")")/python"
    if ! address=$(docker exec "$TARGET" "$python" -I -B -c \
        'from signalblast.settings import Settings; print(Settings().signal_service)' 2>&1); then
        fail "SERVICE UNKNOWN" "${TARGET} couldn't tell the address of signal-cli-rest-api" "$address"
        return 1
    fi
    host=${address%:*}
    port=${address##*:}

    # /etc/hosts comes before the docker DNS, so an extra host could send the address anywhere
    if [ "$(jq '.HostConfig.ExtraHosts // [] | length' "$WORK_DIR/container.json")" -ne 0 ]; then
        fail "SERVICE DIFFERS" "${TARGET} has extra hosts, which could point ${host} to another server" \
            "$(jq -r '.HostConfig.ExtraHosts[]' "$WORK_DIR/container.json")"
        return 1
    fi

    # Only a container on a network of signalblast, with the name of the address on that network, can be the one that
    # the docker DNS resolves the address to. With the host network nothing matches, the address could be anything
    mapfile -t ids < <(docker ps --quiet)
    mapfile -t matches < <(docker container inspect "${ids[@]}" | jq -r --slurpfile signalblast "$WORK_DIR/container.json" \
        --arg host "$host" '($signalblast[0].NetworkSettings.Networks | keys) as $networks
        | .[] | select(any(.NetworkSettings.Networks | to_entries[];
            (.key | IN($networks[])) and ((.value.DNSNames // []) + (.value.Aliases // []) | index([$host]))))
        | .Name | ltrimstr("/")')
    if [ ${#matches[@]} -ne 1 ]; then
        fail "SERVICE DIFFERS" "${TARGET} talks to ${address}, which isn't a single container on its networks" "${matches[@]}"
        return 1
    fi
    API_CONTAINER=${matches[0]}
    docker container inspect --format '{{json .}}' "$API_CONTAINER" > "$WORK_DIR/api-container.json"
    api_port=$(env_var "$WORK_DIR/api-container.json" PORT)
    if [ "$port" != "${api_port:-8080}" ]; then
        fail "SERVICE DIFFERS" "${TARGET} talks to port ${port} of ${API_CONTAINER}, which listens on ${api_port:-8080}"
        return 1
    fi
    report "SERVICE MATCHES" "${TARGET} talks to ${address}, which is container ${API_CONTAINER}"
}

check_api_container() {
    # Checks the signal-cli-rest-api container against the image pinned in the docker-compose.yaml of the release,
    # as its image isn't signed
    local pinned digest id platform
    pinned=$(jq -r '.image' "$WORK_DIR/api-service.json")
    digest=${pinned#*@}
    if [[ $pinned != *@sha256:* ]]; then
        fail "IMAGE UNPINNED" "the docker-compose.yaml of ${TAG} doesn't pin the signal-cli-rest-api image, so it can't be checked"
        return
    fi
    inspect_image "$(jq -r '.Image' "$WORK_DIR/api-container.json")" "$WORK_DIR/api-image.json"
    id=$(jq -r '.Id' "$WORK_DIR/api-image.json")
    platform=$(platform "$WORK_DIR/api-image.json")

    # The pin comes from the signed git tag, so an image id that is the pinned digest needs nothing downloaded.
    # Otherwise the index is downloaded by the pinned digest, so its computed digest can only differ if the registry swapped it
    if [ "$id" != "$digest" ] \
        && ! { matches_image "$WORK_DIR/api-image.json" "${pinned%%:*}" "@${digest}" && [ "$INDEX_DIGEST" = "$digest" ]; }; then
        # The rest of the checks compare the container with its image, which is already the wrong one
        fail "IMAGE DIFFERS" "container ${API_CONTAINER} is not the ${platform} image of ${pinned%@*}, pinned by ${TAG}" \
            "pinned image: ${digest}" "local image:  ${id}"
        return
    fi
    report "IMAGE MATCHES" "container ${API_CONTAINER} is ${pinned%@*} for ${platform}, pinned by ${TAG}"
    check_container "$API_CONTAINER" "$WORK_DIR/api-container.json" "$WORK_DIR/api-image.json" "$WORK_DIR/api-service.json"
    check_devices
}

check_devices() {
    # Every device of the account receives every message, so the bot's own device must be the only one.
    # Asked from inside the signal-cli-rest-api container, with the curl of its image, which was just checked
    local number port output
    number=$(env_var "$WORK_DIR/container.json" SIGNALBLAST_PHONE_NUMBER)
    port=$(env_var "$WORK_DIR/api-container.json" PORT)
    if [ -z "$number" ]; then
        fail "DEVICES UNKNOWN" "${TARGET} doesn't set SIGNALBLAST_PHONE_NUMBER, so the devices of its account can't be listed"
        return
    fi
    if ! output=$(docker exec "$API_CONTAINER" curl -fsS "http://localhost:${port:-8080}/v1/devices/${number}" 2>&1); then
        fail "DEVICES UNKNOWN" "${API_CONTAINER} couldn't list the devices of the bot's account" "$output"
        return
    fi
    if [ "$(jq 'length' <<< "$output")" -eq 1 ]; then
        report "DEVICES MATCH" "the bot's Signal account has no linked devices"
        return
    fi
    fail "LINKED DEVICES" "the bot's Signal account has other devices, which receive every message" \
        "$(jq -r '.[] | "device \(.id) "
            + (.name // "" | if . == "" then "without a name" else "\"\(.)\"" end)
            + ", created on \(.creation_timestamp / 1000 | strftime("%Y-%m-%d"))"
            + ", last seen on \(.last_seen_timestamp / 1000 | strftime("%Y-%m-%d"))"' <<< "$output")"
}

# A running container keeps its image even if the tag was pulled again since, so the image is taken from the container
if docker container inspect --format '{{json .}}' "$TARGET" > "$WORK_DIR/container.json" 2> /dev/null; then
    KIND=container
    image_ref=$(jq -r '.Image' "$WORK_DIR/container.json")
else
    KIND=image
    image_ref=$TARGET
fi
if ! inspect_image "$image_ref" "$WORK_DIR/image.json" 2> /dev/null; then
    echo "Error: there is no container or image called ${TARGET}" >&2
    exit 1
fi
IMAGE_ID=$(jq -r '.Id' "$WORK_DIR/image.json")
PLATFORM=$(platform "$WORK_DIR/image.json")

if [ -n "$TAG" ]; then
    releases=$TAG
    searched="${IMAGE}:$(docker_tag "$TAG")"
else
    echo "Searching the latest ${SEARCH_LIMIT} releases for the image of ${KIND} ${TARGET}"
    # Listed first, so that an error listing them isn't taken as no release matching
    releases=$(gh release list --repo "$GITHUB_REPO" --exclude-drafts --limit "$SEARCH_LIMIT" --json tagName --jq '.[].tagName')
    searched="any of the latest ${SEARCH_LIMIT} releases"
fi
found=false
for TAG in $releases; do
    if matches_image "$WORK_DIR/image.json" "$IMAGE" ":$(docker_tag "$TAG")"; then
        found=true
        break
    fi
done
if ! $found; then
    fail "IMAGE DIFFERS" "${KIND} ${TARGET} is not the ${PLATFORM} image of ${searched}" "local image: ${IMAGE_ID}"
    exit_if_failed "$KIND"
fi
report "IMAGE MATCHES" "${KIND} ${TARGET} is ${IMAGE}:$(docker_tag "$TAG") for ${PLATFORM}"

# The signature is what ties the image to the release, the tag on Docker Hub only says where to find it.
# It is checked for the index that matched, so that Docker Hub isn't asked for it again
verify_image_signature "$TAG" "$WORK_DIR/index.json"

if [ "$KIND" = container ]; then
    # What the containers can add to their images, and the signal-cli-rest-api image, come from the docker-compose.yaml
    # of the release, which is read from its signed git tag
    fetch_tag "$TAG" "$WORK_DIR/src"
    verify_tag "$TAG" "$WORK_DIR/src"
    docker compose -f "$WORK_DIR/src/docker-compose.yaml" config --no-interpolate --format json > "$WORK_DIR/compose.json"
    compose_service signalblast > "$WORK_DIR/service.json"
    compose_service signal-cli-rest-api > "$WORK_DIR/api-service.json"

    check_container "$TARGET" "$WORK_DIR/container.json" "$WORK_DIR/image.json" "$WORK_DIR/service.json"
    if find_api_container; then
        check_api_container
    fi
fi

exit_if_failed "$KIND"

if [ "$KIND" = container ]; then
    echo "${TARGET} runs the signed release ${TAG}, and ${API_CONTAINER} the image that it pins"
    echo "This only shows what the containers run now, see the README for what it can't check"
else
    echo "The image is the signed release ${TAG}"
fi
if $REBUILD; then
    echo "Rebuilding ${TAG} with scripts/verify-release.sh"
    "${SCRIPTS_DIR}/verify-release.sh" "$TAG"
else
    echo "Add --rebuild to also check that the release was built from the code in its git tag"
fi
