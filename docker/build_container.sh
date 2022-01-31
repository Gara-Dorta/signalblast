#!/bin/bash
CURRENT_DIR=$(dirname $(realpath $0))
docker build --build-arg COMMIT_ID=$1 --tag signalblast ${CURRENT_DIR}
