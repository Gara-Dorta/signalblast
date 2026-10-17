#!/bin/bash
# Usage: compose_up.sh [service...], e.g. `compose_up.sh signal-cli-rest-api` to run only signal-cli-rest-api and the
# bot outside docker with `uv run signalblast`. Without arguments it runs all the services.

REPO_DIR=$(dirname "$(dirname "$(realpath "$0")")")

# SIGNALBLAST_VERSION is also used as the version if the image is built via docker compose up
source "${REPO_DIR}/docker/compose_env.sh"

# The rest of the variables are read from a .env file, see .env.example
docker compose -f "${REPO_DIR}/docker-compose.yaml" -f "${REPO_DIR}/docker/compose.dev.yaml" up "$@"
