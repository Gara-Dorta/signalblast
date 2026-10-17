# shellcheck shell=bash
# Sourced by scripts/verify-release.sh and scripts/verify-container.sh, so that both check the requirements, the git tag
# and the image signature the same way, and report the results in the same format.

GITHUB_REPO=Gara-Dorta/signalblast
REPO_URL=https://github.com/${GITHUB_REPO}
IMAGE=eradorta/signalblast
# The keys come from the copy of the repo running the script, not from the release being checked,
# as whoever made the release could have added their own key to it
ALLOWED_SIGNERS="$(dirname "$(dirname "$(realpath "${BASH_SOURCE[0]}")")")/.github/allowed_signers"

check_requirements() {
    # check_requirements <requirement>..., exits if any is missing, so that it is reported before anything is downloaded.
    # A requirement is a command, or docker-buildx, docker-compose, docker-running, gh-attestation or allowed-signers
    local requirement errors=()
    for requirement in "$@"; do
        case $requirement in
            allowed-signers)
                [ -f "$ALLOWED_SIGNERS" ] ||
                    errors+=("$ALLOWED_SIGNERS is missing, clone the repo or copy the script from https://github.com/Gara-Dorta/signalblast/blob/main/.github/allowed_signers") ;;
            docker-*)
                # A missing docker is already reported as a missing command
                if ! command -v docker > /dev/null; then
                    continue
                fi
                case $requirement in
                    docker-buildx) docker buildx version > /dev/null 2>&1 || errors+=("docker buildx is not installed") ;;
                    docker-compose) docker compose version > /dev/null 2>&1 || errors+=("docker compose is not installed") ;;
                    docker-running)
                        docker info > /dev/null 2>&1 || errors+=("docker is not running, or the user can't access it") ;;
                esac
                ;;
            gh-attestation)
                if ! command -v gh > /dev/null; then
                    continue
                elif ! gh attestation --help > /dev/null 2>&1; then
                    errors+=("gh is too old, it has no attestation command, install gh 2.49 or newer")
                elif ! gh auth status > /dev/null 2>&1; then
                    errors+=("gh is not logged in, run gh auth login")
                fi
                ;;
            *) command -v "$requirement" > /dev/null || errors+=("$requirement is not installed") ;;
        esac
    done
    if [ ${#errors[@]} -ne 0 ]; then
        printf 'Error: %s\n' "${errors[@]}" >&2
        exit 1
    fi
}

failed=0
report() {
    # report <result> <text>, aligned so that the texts form a column
    printf '%-19s%s\n' "$1" "$2"
}

fail() {
    # fail <result> <text> [<detail>...], a detail can have several lines, e.g. the output of a command
    local detail line
    report "$1" "$2"
    shift 2
    for detail in "$@"; do
        while IFS= read -r line; do
            if [ -n "$line" ]; then
                report "" "$line"
            fi
        done <<< "$detail"
    done
    failed=1
}

valid() {
    # valid <name> <signer>
    report "SIGNATURE VALID" "$1, signed by $2"
}

invalid() {
    # invalid <name> <error from the verification>
    fail "SIGNATURE INVALID" "$1" "$2"
}

exit_if_failed() {
    # exit_if_failed <what was checked, e.g. release>
    if [ "$failed" -ne 0 ]; then
        echo "The $1 could not be verified"
        exit 1
    fi
}

docker_tag() {
    # docker_tag <release tag>, the same conversion as the release workflow, e.g. v1.2.3+abc is 1.2.3-abc
    local version=${1#v}
    echo "${version//+/-}"
}

fetch_tag() {
    # fetch_tag <release tag> <dir>, checks out the tag in a new repo.
    # Only the tag is fetched, as `git clone --branch` warns that a signed tag "is not a commit"
    git init --quiet "$2"
    git -C "$2" fetch --quiet --depth 1 "$REPO_URL" "refs/tags/$1:refs/tags/$1"
    git -C "$2" -c advice.detachedHead=false checkout --quiet "$1"
}

verify_tag() {
    # verify_tag <release tag> <dir with the tag>, checks that one of the keys in allowed_signers signed the tag
    local output
    if output=$(git -C "$2" -c gpg.ssh.allowedSignersFile="$ALLOWED_SIGNERS" verify-tag "$1" 2>&1); then
        # git reports the fingerprint of the key that made the signature
        valid "Git tag $1" "key $(grep -o 'SHA256:[A-Za-z0-9+/]*' <<< "$output")"
    else
        invalid "Git tag $1" "$output"
    fi
}

verify_image_signature() {
    # verify_image_signature <release tag> <image>, checks that the release workflow signed the image for the tag.
    # The image is an oci://<image>@<digest> reference, or a downloaded image index, whose digest gh computes
    local output name
    name="Docker ${IMAGE}:$(docker_tag "$1")"
    if output=$(gh attestation verify "$2" \
        --repo "$GITHUB_REPO" \
        --signer-workflow "${GITHUB_REPO}/.github/workflows/publish-pypi.yml" \
        --source-ref "refs/tags/$1" 2>&1); then
        valid "$name" "publish-pypi.yml at refs/tags/$1"
    else
        invalid "$name" "$output"
    fi
}
