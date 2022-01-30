FROM signald/signald

RUN apt update && apt upgrade -y

RUN apt install -y python3-pip netcat-openbsd

RUN pip install semaphore-bot

RUN git clone https://github.com/Garoe/signalblast

RUN mkdir /var/run/signald

