#!/bin/bash

# Create the wheel for signalblast
uv build

SIGNALBLAST_VERSION=$(uvx hatch version)

# Replace the + for a -, as + is not a valid docker tag
export DOCKER_TAG="${SIGNALBLAST_VERSION//+/-}"

docker compose build --progress=plain --build-arg SIGNALBLAST_VERSION=$SIGNALBLAST_VERSION ${REPO_DIR}
