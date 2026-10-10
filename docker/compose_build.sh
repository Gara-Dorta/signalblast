#!/bin/bash
REPO_DIR=$(dirname $(dirname $(realpath $0)))

# The wheel is built inside the image, the version is passed in as git is not available there
SIGNALBLAST_VERSION=$(uvx hatch version)

# Use the commit time instead of the current time, so that the build is reproducible
SOURCE_DATE_EPOCH=$(git -C "${REPO_DIR}" log -1 --format=%ct)

# Replace the + for a -, as + is not a valid docker tag
export DOCKER_TAG="${SIGNALBLAST_VERSION//+/-}"

docker compose --file "${REPO_DIR}/docker-compose.yaml" build --progress=plain --build-arg SIGNALBLAST_VERSION=$SIGNALBLAST_VERSION --build-arg SOURCE_DATE_EPOCH="$SOURCE_DATE_EPOCH" signalblast
