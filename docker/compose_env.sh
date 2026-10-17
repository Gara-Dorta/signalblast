# shellcheck shell=bash
# Sourced by compose_build.sh and compose_up.sh, sets the variables that docker-compose.yaml reads.

# The wheel is built inside the image, the version is passed in as git is not available there
SIGNALBLAST_VERSION=$(cd "$(dirname "${BASH_SOURCE[0]}")" && uvx hatch version)
export SIGNALBLAST_VERSION

# Replace the + for a -, as + is not a valid docker tag
export DOCKER_TAG="${SIGNALBLAST_VERSION//+/-}"
