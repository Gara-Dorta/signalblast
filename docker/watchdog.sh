#!/bin/sh

# Restart signal-cli-rest-api and signalblast when the signalblast container is unhealthy.
# signal-cli-rest-api can report healthy while being unable to send messages, and that is
# only recoverable by restarting both containers.
# The health check itself is defined in the signalblast Dockerfile, this script only reads its status.
# It runs on the host so that no container needs access to the docker socket.
# Run it periodically with systemd/signalblast-watchdog.timer

API_CONTAINER="${SIGNAL_API_CONTAINER:-signal-cli-rest-api}"
BOT_CONTAINER="${SIGNALBLAST_CONTAINER:-signalblast}"

status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$BOT_CONTAINER" 2>/dev/null)"

# Only act on unhealthy, a missing or stopped container is handled by its restart policy
if [ "$status" != "unhealthy" ]; then
    echo "$BOT_CONTAINER health status: ${status:-unknown}, nothing to do"
    exit 0
fi

echo "$BOT_CONTAINER is unhealthy, restarting containers"

docker restart "$API_CONTAINER" || exit 1

# Wait up to 5 minutes for the api to be healthy, otherwise signalblast fails to start
for _ in $(seq 60); do
    if [ "$(docker inspect -f '{{.State.Health.Status}}' "$API_CONTAINER")" = "healthy" ]; then
        break
    fi
    sleep 5
done

docker restart "$BOT_CONTAINER"
