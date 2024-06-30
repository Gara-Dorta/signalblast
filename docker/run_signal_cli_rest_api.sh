#!/bin/bash

docker run --name signal-api-json-rpc -p 8080:8080 \
    --restart=unless-stopped \
    -v $HOME/.local/share/signal-api:/home/.local/share/signal-cli \
    -e 'MODE=json-rpc' \
    -e 'AUTO_RECEIVE_SCHEDULE_SEND_READ_RECEIPTS=true' \
    bbernhard/signal-cli-rest-api:0.85
