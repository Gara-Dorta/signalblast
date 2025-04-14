# signalblast

Signalblast is a tool to send encrypted messages anonymously over [Signal](https://www.signal.org/) to a subscriber list. The sender does not know who the subscribers in the list are, nor the subscribers know who the sender is.

A server is required to host the bot, find instructions on how the set it up below.

The idea for this bot came from [Signalboost](https://web.archive.org/web/https://signalboost.info/), which unfortunately is no longer alive.

## Usage

Once the bot is up and running, several commands are available:
* `!subscribe` send this to sign up to the list
* `!broadcast` after subscribing any message preceded by this will be broadcasted to every subscriber
* `!unsubscribe` to stop receiving messages
* `!help` to be reminded of which commands are available
* `!admin` send a message only to the list admin, useful for getting technical support

## Installation

### Option 1: local python environment
* Set up signalbot as specified [here](https://github.com/filipre/signalbot)
* Create a new virtual environment, [uv](https://docs.astral.sh/uv/) is recommended
* Install with `pip install signalblast`
* Run via `python -m signalblast.main`

### Option 2: docker compose
This will pull the project docker images from https://hub.docker.com/r/eradorta/signalblast

* Install [docker](https://www.docker.com/).
* Download the [docker-compose.yml](https://github.com/Era-Dorta/signalblast/blob/main/docker-compose.yaml) file.
* Create a folder called `signalblast_data`
* Define the relevant environment variables
  ```bash
  export DOCKER_TAG="The version of signalblast to run, can be latest"
  export SIGNALBLAST_PHONE_NUMBER="The phone number of the bot"
  export SIGNALBLAST_PASSWORD="The password for the admin"
  export SIGNALBLAST_HEALTHCHECK_RECEIVER="The contact or group to send health check messages"
  ```
* Run via docker compose: `docker compose up`

## Development

* Set up docker and signalbot as specified in the [installation](#installation) section.
* Clone the repo
* Install [uv](https://docs.astral.sh/uv/)
* Install the repo and the dependencies in a new virtual environment with `uv sync`
* Install the pre-commit hook `uv run pre-commit install`
* Run
  * Directly via `uv run python -m signalblast.main`
  * Via systemd with `systemd/signalblast.service`
    * Run once with the password in the env file.
    * From there one, the password is stored encrypted and it can be removed from the env file
* Optional: install signalbot as an editable dependency `uv add --editable ../signalbot/`

### Docker compose

The `docker/compose_build.sh` and `docker/compose_up.sh` are provide for easier development.

## Roadmap

* Make instructions clearer and add pictures to the readme
* Add unit testing
