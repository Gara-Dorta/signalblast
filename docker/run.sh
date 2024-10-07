#!/bin/bash

# Add these for easier development
#  -v $(dirname ${REPO_DIR}):/home/user/signalblast/ \
#  --interactive=true \
#  --tty=true \
#  --entrypoint bash \

SIGNALBLAST_BASE="${SIGNALBLAST_BASE:-$(pwd)}"

REPO_DIR=$(dirname $(dirname $(realpath $0)))
docker container run \
  --rm \
 -v $HOME/.local/share/signal-api/:/home/user/.local/share/signal-api/ \
 --interactive=true \
 --tty=true \
 --entrypoint bash \
 --network host \
  eradorta/signalblast:0.5.0
