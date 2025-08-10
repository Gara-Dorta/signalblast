#!/bin/bash

docker run --rm -p 8080:8080 \
    -v $HOME/.local/share/signal-api:/home/.local/share/signal-cli \
    -e MODE='json-rpc' \
    bbernhard/signal-cli-rest-api:0.94
