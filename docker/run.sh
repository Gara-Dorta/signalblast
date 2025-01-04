#!/bin/bash

# Add these for easier development
# REPO_DIR=$(dirname $(dirname $(realpath $0)))
#
#  -v $(dirname ${REPO_DIR}):/home/user/signalblast/ \
#  --interactive=true \
#  --tty=true \
#  --entrypoint bash \

SIGNALBLAST_VERSION=$(uvx hatch version)
DOCKER_TAG="${SIGNALBLAST_VERSION//+/-}"

docker run \
 --rm \
 -v $HOME/.local/share/signal-api/:/home/user/.local/share/signal-api/ \
 --network host \
 -e SIGNALBLAST_PHONE_NUMBER='PHONE_NUMBER' \
 -e SIGNALBLAST_PASSWORD='PASSWORD' \
  eradorta/signalblast:$DOCKER_TAG
