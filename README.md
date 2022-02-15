# signalblast

* Get the docker image from docker hub
* Run a container that uses the image
  * `$ ./docker/run_container.sh`
* Open a second terminal inside the container to configure the bot
  * `$ docker exec -it <container name> bash`
* Add the bot phone number to the config file
  * `$ micro ./signalblast/docker/phone_number.sh`
  * `$ source ./signalblast/docker/phone_number.sh`
* Link **or** register the phone number
  * Linking (recommended)
    * Run the link command and scan the QR code
      * `$ signaldctl account link $"SIGNAL_PHONE_NUMBER"`
  * Registering (not recommended)
    * Get the captcha helper from here https://gitlab.com/signald/captcha-helper
      * Run captcha helper `$ ./signal-captcha-helper`
    * Register the account using the captcha (substitue nnnnn for the captcha output)
      * `$ signaldctl account register $"SIGNAL_PHONE_NUMBER" --captcha nnnnn`
    * Verify the account (substitute nnnnn for the sms verification code)
      * `$ signaldctl account verify $"SIGNAL_PHONE_NUMBER" nnnnn`
* Send message to the bot, a good first message is `!help`. The bot should reply inmediately.
* If this is not the case, check the logs at `/var/log/signalblast/log`
