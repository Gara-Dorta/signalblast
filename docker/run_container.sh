#!/bin/bash
docker container run -v $(pwd)/run:/signald --interactive=true --tty=true signalblast:latest /bin/bash
