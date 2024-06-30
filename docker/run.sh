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
 -v $(dirname ${REPO_DIR}):/home/user/signalblast/ \
 --interactive=true \
 --tty=true \
 --entrypoint bash \
  eradorta/signalblast:0.0.1.dev0
