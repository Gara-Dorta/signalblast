#!/bin/bash

# Add this line to mount points for easier development
# -v $(dirname ${CURRENT_DIR})/src:/home/gradle/signalblast/src \

CURRENT_DIR=$(dirname $(realpath $0))
docker container run \
  -v ${CURRENT_DIR}/run:/signald \
  --interactive=true \
  --tty=true \
  signalblast:latest /bin/bash
