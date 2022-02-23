#!/bin/bash
CURRENT_DIR=$(dirname $(realpath $0))

if [ "$#" -ne 1 ]; then
    echo "Error: Missing commit_id argument"
    exit 1
fi

docker build --build-arg COMMIT_ID=$1 --tag eraxama/signalblast ${CURRENT_DIR}
