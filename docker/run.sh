#!/bin/bash
REPO_DIR=$(dirname $(dirname $(realpath $0)))

# Add these for easier development
#  -v ${REPO_DIR}:/home/user/signalblast/ \
#  --interactive=true \
#  --tty=true \
#  --entrypoint bash \

SIGNALBLAST_VERSION=$(uvx hatch version)
DOCKER_TAG="${SIGNALBLAST_VERSION//+/-}"

# The environment variables are read from the .env file in the repo, see .env.example
docker run \
 --rm \
 -v $HOME/.local/share/signalblast/:/home/user/.local/share/signalblast/ \
 --network host \
 --env-file "${REPO_DIR}/.env" \
  eradorta/signalblast:$DOCKER_TAG
