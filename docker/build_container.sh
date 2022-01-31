#!/bin/bash
docker build --build-arg COMMIT_ID=$1 --tag signalblast .
