#!/bin/bash

# SIGNALBLAST_VERSION is also used as the version if the image is built via docker compose up
source "$(dirname "$(realpath "$0")")/compose_env.sh"

# The rest of the variables are read from a .env file, see .env.example
docker compose up
