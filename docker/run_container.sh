#!/bin/bash

# Add these for easier development
#  -v $(dirname ${CURRENT_DIR}):/home/user/signalblast/ \
#  --interactive=true \
#  --tty=true \
#  --entrypoint bash \

SIGNALBLAST_BASE="${SIGNALBLAST_BASE:-$(pwd)}"

CURRENT_DIR=$(dirname $(realpath $0))
docker container run \
  --restart=unless-stopped \
  -v "${SIGNALBLAST_BASE}/data/signalblast:/home/user/signalblast/signalblast/data" \
  -v "${SIGNALBLAST_BASE}/data/signald:/home/user/signald" \
  -e SIGNAL_PHONE_NUMBER="" \
  eraxama/signalblast:latest
