#!/bin/bash
REPO_DIR=$(dirname "$(dirname "$(realpath "$0")")")

source "${REPO_DIR}/docker/compose_env.sh"

docker compose --file "${REPO_DIR}/docker-compose.yaml" build --progress=plain signalblast
