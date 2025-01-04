#!/bin/bash
REPO_DIR=$(dirname $(dirname $(realpath $0)))

# Create the wheel for signalblast
uv build

SIGNALBLAST_VERSION=$(uvx hatch version)

# Replace the + for a -, as + is not a valid docker tag
DOCKER_TAG="${SIGNALBLAST_VERSION//+/-}"

docker build \
--progress=plain \
--network=host \
--build-arg SIGNALBLAST_VERSION=$SIGNALBLAST_VERSION \
--tag eradorta/signalblast:$DOCKER_TAG \
${REPO_DIR}
