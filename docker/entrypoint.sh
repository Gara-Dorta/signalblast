#!/bin/bash

SIGNALBLAST_LOG_FILE="/var/log/signalblast.log"

export SIGNALD_TRUST_NEW_KEYS=true

signald &> /var/log/signald.log &

# Signald needs some time to start up
sleep 5s

# Wait for the user to link their phone with signald
while [[ "$(signaldctl account list --output-format yaml)" == "[]" ]]; do
    sleep 3
    echo "Waiting for account registration" >> $SIGNALBLAST_LOG_FILE
done

echo "An account was registered" >> $SIGNALBLAST_LOG_FILE

source /root/signalblast/docker/phone_number.sh

# Signald needs again some time after phone linking
echo "Waiting for signald to get ready" >> $SIGNALBLAST_LOG_FILE
sleep 15s
echo "Starting the signalblast bot" >> $SIGNALBLAST_LOG_FILE

python3 /root/signalblast/signalblast/broadcastbot.py

