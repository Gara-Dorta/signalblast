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
* Create a virtual environment
* Clone the repo git
* Install with `poetry install`
* Run
  * Directly via `python -m signalblast.main`
  * Via systemd with `systemd/signalblast.service`
    * Run once with the password in the env file.
    * From there one, the password is stored encrypted and it can be removed from the env file
