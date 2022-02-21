# signalblast

* Get the docker image from docker hub
* Run a container that uses the image
  * `$ ./docker/run_container.sh`
  * Optionally set the admin password and the expiration time, if only one argument is provided it is assumed to be the password.
   * `$ ./docker/run_container.sh <password> <expiration time>`
* Open a second terminal inside the container to configure the bot
  * `$ docker exec -it <container name> bash`
* Add the bot phone number to the config file
  * Replace `123456789` with your bot phone number, including the country code
  * `$ sed -i 's/SIGNAL_PHONE_NUMBER=/SIGNAL_PHONE_NUMBER=+123456789/g' /root/signalblast/signalblast/data/phone_number.sh`
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
