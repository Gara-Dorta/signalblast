FROM ubuntu:22.04

RUN apt-get update

# Additional upgade, good for safety but optional
# RUN apt-get upgrade -y

RUN apt-get install -y python3-pip netcat-openbsd git

# This uid is the same uid as the non-root user in the signald container, if that changes, it should be changed here too.
RUN useradd --create-home --shell /bin/bash --uid 1337 user

USER user

WORKDIR /home/user

ARG COMMIT_ID

RUN git clone https://github.com/Era-Dorta/signalblast && cd signalblast && git checkout $COMMIT_ID

RUN pip install install -r ./signalblast/requirements.txt

# Install semaphore from git, needed if adding changes to it before they get published
# RUN pip install git+https://github.com/lwesterhof/semaphore.git

# For development, run as root, as it is the only way to get the files to be owned by the user
# USER root
# RUN pip install install -r ./signalblast/requirements.txt

ENTRYPOINT ["/home/user/signalblast/docker/entrypoint.sh"]
