#!/bin/bash

export SIGNALD_TRUST_NEW_KEYS=true

signald &> /var/log/signald.log &

while [[ "$(signaldctl account list --output-format yaml)" == "[]" ]]; do
    sleep 3
    echo "waiting for account setup"
done

source /root/signalblast/phone_number.sh

echo $SIGNAL_PHONE_NUMBER

python3 /root/signalblast/signalblast/broadcastbot.py;

