#!/bin/bash

SIGNALBLAST_VERSION=$(uvx hatch version)

# Replace the + for a -, as + is not a valid docker tag
export DOCKER_TAG="${SIGNALBLAST_VERSION//+/-}"

export SIGNALBLAST_PHONE_NUMBER=""
export SIGNALBLAST_PASSWORD=""

docker compose up
