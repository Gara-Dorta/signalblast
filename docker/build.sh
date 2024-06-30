#!/bin/bash
REPO_DIR=$(dirname $(dirname $(realpath $0)))

docker build \
--progress=plain \
--target dev \
--tag eradorta/signalblast:0.0.1.dev0 \
${REPO_DIR}
