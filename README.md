# signalblast

signald

nc -U /var/run/signald/signald.sock


Get captcha helper from here https://gitlab.com/signald/captcha-helper

{"type": "register", "version": "v1", "account": "+xxxxxxxxxxx", "captcha" : "yyyyyyyyyyyyyyy"}

{"type": "verify", "version": "v1", "account": "+xxxxxxxxxxx", "code": "zzzzzz"}

{"type": "send", "version": "v1", "username": "+xxxxxxxxxxx", "recipientAddress": {"number": "+yyyyyyyyyyy"}, "messageBody": "Hello world"}
