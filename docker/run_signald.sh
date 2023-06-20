#!/bin/bash

SIGNALD_BASE="${SIGNALD_BASE:-$(pwd)}"

docker run \
-v "${SIGNALD_BASE}/data/signald:/signald" \
-e SIGNALD_TRUST_NEW_KEYS=true \
-e SIGNALD_TRUST_ALL_KEYS=true \
registry.gitlab.com/signald/signald:0.23.2
