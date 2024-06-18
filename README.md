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

* Set up signalbot as specified [here](https://github.com/filipre/signalbot)
* Once signald is configured, lets run a container with signalblast
  * ```bash
       docker container run \
       --restart=unless-stopped \
       -v "./data/signalblast:/home/user/signalblast/signalblast/data" \
       -v "./data/signald:/home/user/signald" \
       -e SIGNAL_PHONE_NUMBER=<Your phone number> \
       eraxama/signalblast:latest
    ```
  * There are two optional parameters
    * `-e SIGNALBLAST_PASSWORD=<a password>` -> the admin password for signalblast
    * `-e SIGNALBLAST_EXPIRATION_TIME=<time>` -> an automatic message expiration time in seconds
* Now you can send message to the bot, a good first message is `!help`. The bot should reply immediately.
* If this is not the case, check the logs at `./data/signalblast/signalblast.log`
