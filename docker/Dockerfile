FROM signald/signald

ARG COMMIT_ID

WORKDIR /root

RUN apt update && apt upgrade -y

RUN apt install -y python3-pip netcat-openbsd

RUN pip install semaphore-bot argparse bcrypt

RUN git clone https://github.com/Garoe/signalblast && cd signalblast && git checkout $COMMIT_ID

RUN mkdir /var/run/signald

RUN echo "socketpath: /var/run/signald/signald.sock" >> /root/.config/signaldctl.yaml

CMD ["./signalblast/docker/entrypoint.sh"]
