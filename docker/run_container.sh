#!/bin/bash

# Add these for easier development
# -v $(dirname ${CURRENT_DIR}):/root/signalblast/ \
#   --interactive=true \
#   --tty=true \

SIGNALBLAST_BASE="${SIGNALBLAST_BASE:-$(pwd)}"

CURRENT_DIR=$(dirname $(realpath $0))
docker container run \
  --restart=unless-stopped \
  -v "${SIGNALBLAST}/signalblast_data:/root/signalblast/signalblast/data" \
  -v "${SIGNALBLAST}/signald_data:/root/.config/signald" \
  signalblast:latest "$@"
