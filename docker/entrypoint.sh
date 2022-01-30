#!/bin/bash

signald &

# TODO write some code to the registration automatically here
# In between should do the registration
# nc -U /var/run/signald/signald.sock

python ./broadcastbot.py
