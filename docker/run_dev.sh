#!/bin/bash
REPO_DIR=$(dirname $(dirname $(realpath $0)))

SIGNALBLAST_VERSION=$(uvx hatch version)
DOCKER_TAG="${SIGNALBLAST_VERSION//+/-}"

echo $REPO_DIR

# The environment variables are read from the .env file in the repo, see .env.example
docker run \
 --rm \
 -v $HOME/.local/share/signalblast/:/home/user/.local/share/signalblast/ \
 -v $REPO_DIR:/home/user/signalblast \
 --interactive=true \
 --tty=true \
 --entrypoint bash \
 --network host \
 --env-file "${REPO_DIR}/.env" \
  eradorta/signalblast:$DOCKER_TAG
