# signalblast

Signalblast is a tool to send encrypted messages anonymously over [Signal](https://www.signal.org/) to a subscriber list. The sender does not know who the subscribers in the list are, nor the subscribers know who the sender is.

A server is required to host the bot, find instructions on how the set it up below.

The idea for this bot came from [Signalboost](https://web.archive.org/web/https://signalboost.info/), which unfortunately is no longer alive.

## Usage

Once the server is up and running, several commands are available:
* `!subscribe` send this to sign up to the list
* `!broadcast` after subscribing any message preceded by this will be broadcasted to every subscriber
* `!unsubscribe` to stop receiving messages
* `!help` to be reminded of which commands are available
* `!admin` send a message only to the list admin, useful for getting technical support

## Installation

The only required dependency is [docker](https://www.docker.com/).

* Once docker is installed, get the signalblast image from docker hub
  * ```bash
    docker pull eraxama/signalblast
    ```
* Run a container that uses the image
  * ```bash
       docker container run \
       --restart=unless-stopped \
       -v "./data/signalblast:/root/signalblast/signalblast/data" \
       -v "./data/signald:/root/.config/signald" \
       signalblast:latest <admin password> <expiration time>
    ```
  * The admin password and the expiration time (in seconds) parameters are optional. If only one argument is provided it is assumed to be the password.
* Open a second terminal inside the container to configure the bot
  * ```bash
    docker exec -it <container name> bash
    ```
  * If you don't know the name of the container, run `docker container list` to find out.
* Add the bot phone number to the config file
  * Replace `123456789` with your bot phone number, including the country code
  * ```bash
    sed -i 's/SIGNAL_PHONE_NUMBER=/SIGNAL_PHONE_NUMBER=+123456789/g' /root/signalblast/signalblast/data/phone_number.sh
    ```
    ```bash
    source /root/signalblast/signalblast/data/phone_number.sh
    ```
* Link **or** register the phone number
  * Linking (easier)
    * Run the link command and scan the QR code
      * ```bash
        signaldctl account link $"SIGNAL_PHONE_NUMBER"
        ```
  * Registering (harder)
    * Get the captcha helper from here https://gitlab.com/signald/captcha-helper
      * Run captcha helper ```bash
                           ./signal-captcha-helper
                           ```
    * Register the account using the captcha (substitue nnnnn for the captcha output)
      * ```bash
        signaldctl account register $"SIGNAL_PHONE_NUMBER" --captcha nnnnn
        ```
    * Verify the account (substitute nnnnn for the sms verification code)
      * ```bash
        signaldctl account verify $"SIGNAL_PHONE_NUMBER" nnnnn
        ```
* Send message to the bot, a good first message is `!help`. The bot should reply immediately.
* If this is not the case, check the logs at `/var/log/signalblast.log`
