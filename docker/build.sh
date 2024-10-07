#!/bin/bash
REPO_DIR=$(dirname $(dirname $(realpath $0)))
SIGNALBLAST_VERSION=0.5.0

docker build \
--progress=plain \
--target base \
--build-arg SIGNALBLAST_VERSION=$SIGNALBLAST_VERSION \
--tag eradorta/signalblast:$SIGNALBLAST_VERSION \
${REPO_DIR}
