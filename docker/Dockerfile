FROM signald/signald

WORKDIR /root

RUN apt update && apt upgrade -y

RUN apt install -y python3-pip netcat-openbsd

RUN pip install argparse bcrypt # semaphore-bot install semaphore from git until changes are merged

RUN pip install git+https://github.com/Era-Dorta/semaphore.git@expiration-and-attachments

ARG COMMIT_ID

RUN git clone https://github.com/Era-Dorta/signalblast && cd signalblast && git checkout $COMMIT_ID

RUN mkdir /var/run/signald

RUN echo "socketpath: /var/run/signald/signald.sock" >> /root/.config/signaldctl.yaml

CMD ["/root/signalblast/docker/entrypoint.sh"]
