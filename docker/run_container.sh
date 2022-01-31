#!/bin/bash
CURRENT_DIR=$(dirname $(realpath $0))
docker container run \
  -v ${CURRENT_DIR}/run:/signald \
  \ # -v $(dirname ${CURRENT_DIR})/src:/home/gradle/signalblast/src \ # Uncomment this line for develop
  --interactive=true \
  --tty=true \
  signalblast:latest /bin/bash
