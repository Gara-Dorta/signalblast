FROM ubuntu:22.04

# RUN apt-get update && apt-get upgrade -y
RUN apt-get update

RUN apt-get install -y python3-pip netcat-openbsd git

RUN useradd --create-home --shell /bin/bash --uid 1337 user

USER user

WORKDIR /home/user

RUN pip install argparse bcrypt # semaphore-bot install semaphore from git until changes are merged

RUN pip install git+https://github.com/lwesterhof/semaphore.git

ARG COMMIT_ID

RUN git clone https://github.com/Era-Dorta/signalblast && cd signalblast && git checkout $COMMIT_ID

# USER root # For development, run as root, as it is the only way to get the files to be owned by the user

ENTRYPOINT ["/home/user/signalblast/docker/entrypoint.sh"]
