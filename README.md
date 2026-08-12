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
* Set up signalbot as specified [here](https://github.com/signalbot-org/signalbot)
* Create a new virtual environment, [uv](https://docs.astral.sh/uv/) is recommended
* Install with
  ```bash
  pip install signalblast
  ```
* Run via
  ```bash
  python -m signalblast.main
  ```

### Option 2: docker compose
This will pull the project docker images from https://hub.docker.com/r/eradorta/signalblast

* Install [docker](https://www.docker.com/).
* Configure signal-cli-rest-api as specified [here](https://signalbot-org.github.io/signalbot/latest/getting_started/#setup-signal-cli-rest-api)
* Download the [docker-compose.yml](https://github.com/Gara-Dorta/signalblast/blob/main/docker-compose.yaml) and [.env.example](https://github.com/Gara-Dorta/signalblast/blob/main/.env.example) files.
* Create a data folder
  ```bash
  mkdir -p $HOME/.local/share/signalblast
  ```
* Create your `.env` file from the example and fill in the values
  ```bash
  cp .env.example .env
  ```
* Run via docker compose:
  ```bash
  docker compose up
  ```

### Migrating from CSV (pre-v2)

Older versions of signalblast stored subscribers, banned users and the admin in `subscribers.csv`, `banned_users.csv` and `admin.txt` inside the data folder. These have been replaced with a sqlite database (`signalblast.db`, in the same data folder).

If you're upgrading from a version that still has these files, migrate them once with:
```bash
uv run python -m signalblast.migrate_csv_to_db
```
This only adds data to the database; it never modifies or deletes the original CSV/txt files. Run it, confirm the bot works as expected, then you can delete `subscribers.csv`, `banned_users.csv` and `admin.txt` manually.

## Development

* Set up docker and signalbot as specified in the [installation](#installation) section.
* Clone the repo
* Install [uv](https://docs.astral.sh/uv/)
* Install the repo and the dependencies in a new virtual environment with `uv sync`
* Install the prek hook `uv run prek install`
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
