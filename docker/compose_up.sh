#!/bin/bash

# Also used as the version if the image is built via docker compose up
export SIGNALBLAST_VERSION=$(uvx hatch version)

# Replace the + for a -, as + is not a valid docker tag
export DOCKER_TAG="${SIGNALBLAST_VERSION//+/-}"

# The rest of the variables are read from a .env file, see .env.example
docker compose up
