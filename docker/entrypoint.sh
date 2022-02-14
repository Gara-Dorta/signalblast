#!/bin/bash

# export SIGNAL_PHONE_NUMBER=

if [ -z ${SIGNAL_PHONE_NUMBER+x} ];
then
    signald
else
    signald &
    python3 /root/signalblast/signalblast/broadcastbot.py;
fi
