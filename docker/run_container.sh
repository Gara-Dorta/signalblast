#!/bin/bash

# Add this line to mount points for easier development
# -v $(dirname ${CURRENT_DIR}):/root/signalblast/ \

CURRENT_DIR=$(dirname $(realpath $0))
docker container run \
  --restart=unless-stopped \
  --interactive=true \
  --tty=true \
  signalblast:latest "$@"
