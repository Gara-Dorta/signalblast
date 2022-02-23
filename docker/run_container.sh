#!/bin/bash

# Add these for easier development
#  -v $(dirname ${CURRENT_DIR}):/root/signalblast/ \
#  --interactive=true \
#  --tty=true \
#  --entrypoint bash \

SIGNALBLAST_BASE="${SIGNALBLAST_BASE:-$(pwd)}"

CURRENT_DIR=$(dirname $(realpath $0))
docker container run \
  --restart=unless-stopped \
  -v "${SIGNALBLAST_BASE}/data/signalblast:/root/signalblast/signalblast/data" \
  -v "${SIGNALBLAST_BASE}/data/signald:/root/.config/signald" \
  eraxama/signalblast:latest "$@"
