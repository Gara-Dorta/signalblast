#!/bin/bash

# Uncoment to build the wheel and be able to build the images via docker compose up
# uv build

export SIGNALBLAST_VERSION=$(uvx hatch version)

# Replace the + for a -, as + is not a valid docker tag
export DOCKER_TAG="${SIGNALBLAST_VERSION//+/-}"

export SIGNALBLAST_PHONE_NUMBER=""
export SIGNALBLAST_PASSWORD=""
export SIGNALBLAST_HEALTHCHECK_RECEIVER=""
export SIGNALBLAST_WELCOME_MESSAGE=""
export SIGNALBLAST_INSTRUCTIONS_URL=""

docker compose up
