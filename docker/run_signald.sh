#!/bin/bash

SIGNALD_BASE="${SIGNALD_BASE:-$(pwd)}"

docker run -v "${SIGNALD_BASE}/data/signald:/signald" signald/signald:0.18.0
