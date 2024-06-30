FROM python:3.10

RUN apt update

# Additional upgade, good for safety but optional
# RUN apt upgrade -y

RUN apt install -y netcat-openbsd --no-install-recommends

# This uid is the same uid as the non-root user in the signal-cli-rest-api container
RUN useradd --create-home --shell /bin/bash --uid 1000 user

USER user

WORKDIR /home/user

ARG COMMIT_ID

RUN git clone https://github.com/Era-Dorta/signalblast && cd signalblast && git checkout $COMMIT_ID

RUN python3 -m pip install install -r ./signalblast/requirements.txt

ENTRYPOINT ["/home/user/signalblast/docker/entrypoint.sh"]
