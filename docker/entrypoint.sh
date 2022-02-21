#!/bin/bash

# Copy template phone number file if it does not exist in the data folder
SIGNALBLAST_PHONE_NUMBER_FILE="/root/signalblast/signalblast/data/signalblast/phone_number.sh"
if [ ! -f ${SIGNALBLAST_PHONE_NUMBER_FILE} ]; then
  cp "/root/signalblast/docker/phone_number.sh" ${SIGNALBLAST_PHONE_NUMBER_FILE}
fi

export SIGNALD_TRUST_NEW_KEYS=true

signald &> /var/log/signald.log &

# Signald needs some time to start up
sleep 5s

SIGNALBLAST_LOG_FILE="/var/log/signalblast.log"

# Wait for the user to link their phone with signald
while [[ "$(signaldctl account list --output-format yaml)" == "[]" ]]; do
    sleep 3
    echo "Waiting for account registration" >> $SIGNALBLAST_LOG_FILE
done

echo "An account was registered" >> $SIGNALBLAST_LOG_FILE

source ${SIGNALBLAST_PHONE_NUMBER_FILE}

# Signald needs again some time after phone linking
echo "Waiting for signald to get ready" >> $SIGNALBLAST_LOG_FILE
sleep 15s
echo "Starting the signalblast bot" >> $SIGNALBLAST_LOG_FILE

BROADCAST_BOT_CMD="python3 /root/signalblast/signalblast/broadcastbot.py"

if [ "$#" -eq 1 ]; then
  BROADCAST_BOT_CMD="$BROADCAST_BOT_CMD --admin_pass "$1""
fi

if [ "$#" -eq 2 ]; then
  BROADCAST_BOT_CMD="$BROADCAST_BOT_CMD --admin_pass "$1" --expiration_time "$2""
fi

if [ "$#" -gt 2 ]; then
  echo "Recieved too many arguments" >> $SIGNALBLAST_LOG_FILE
  exit 1
fi

eval $BROADCAST_BOT_CMD
