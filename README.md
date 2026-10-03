# signalblast

Signalblast is a bot that sends encrypted messages anonymously over [Signal](https://www.signal.org/) to a list of subscribers. Subscribers don't see who else is on the list, and they don't see who sent a broadcast: every message comes from the bot.

A server is required to host the bot, see the [installation](#installation) instructions below.

The idea for this bot came from [Signalboost](https://web.archive.org/web/https://signalboost.info/), which unfortunately is no longer alive.

## Usage

Send these commands to the bot in a private chat. Commands are not case sensitive.

* `!subscribe` sign up to the list
* `!unsubscribe` stop receiving messages
* `!broadcast <message>` send a message to every subscriber. Any message that isn't a command is broadcast too, so `!broadcast` is only needed for messages that start with `!`
* `!admin <message>` send a message only to the admins, e.g. to get technical support
* `!help` show the available commands

Broadcasts can be edited and deleted for everyone in Signal as usual, for up to 24 hours. Messages that start with `!` but aren't a command are never broadcast, the bot replies with the help instead.

### Admin commands

* `!add admin <password>` become an admin, the password is `SIGNALBLAST_PASSWORD`. There can be several admins
* `!remove admin <password> <admin id>` remove an admin
* `!list admins` show the ids of the admins
* `!ban` quote a broadcast, or a message from a user, and send `!ban` to ban its sender. This works for broadcasts from the last 24 hours (so the admin must be subscribed to receive them) and for messages from the last 7 days
* `!list bans` show the banned users, numbered, with the start of the message they were banned for
* `!lift ban <number>` lift a ban
* `!version` show the versions of signalblast, signalbot and signal-cli-rest-api

Messages that users send with `!admin` reach every admin as `User wrote: …`. To reply, quote the message and write the reply, without any command. The user receives it as `Admin: …` and answers the same way, by quoting it, and so on. The other admins get a copy of every reply. Each message the bot sends in a conversation quotes the message it answers, so every chat shows the conversation as a thread. Quoting any message of a conversation continues it, it is never broadcast.

### Privacy

* Subscribers never learn who else is subscribed, or who sent a broadcast.
* Admins never learn who a subscriber is either: users who write to the admins appear as `User`, and bans and replies work by quoting messages.
* The server running the bot does know who everyone is. Its database stores who sent each broadcast for 24 hours (to allow edits, deletes and bans), and which user each message between users and admins belongs to for 7 days (not its content). Subscriber ids only appear in the logs with `SIGNALBLAST_LOG_LEVEL=DEBUG`.

## Installation

### Option 1: docker compose

This uses the images from https://hub.docker.com/r/eradorta/signalblast

* Install [docker](https://www.docker.com/).
* Set up signal-cli-rest-api for the bot's phone number as specified [here](https://signalbot-org.github.io/signalbot/latest/getting_started/#setup-signal-cli-rest-api).
* Download the [docker-compose.yaml](https://github.com/Gara-Dorta/signalblast/blob/main/docker-compose.yaml) and [.env.example](https://github.com/Gara-Dorta/signalblast/blob/main/.env.example) files.
* Create a data folder
  ```bash
  mkdir -p $HOME/.local/share/signalblast
  ```
* Create your `.env` file from the example and fill in the values, see [configuration](#configuration). `DOCKER_TAG` and `SIGNAL_CLI_REST_API_VERSION` set the versions of signalblast and signal-cli-rest-api that run.
  ```bash
  cp .env.example .env
  ```
* Run via docker compose:
  ```bash
  docker compose up
  ```
* Optional: restart the containers automatically when signalblast can't send messages.
  * Set `SIGNALBLAST_HEALTHCHECK_RECEIVER` in your `.env` file, it will receive a "Ping" message every 8 hours. The signalblast container is reported as unhealthy after 3 failed pings in a row, so a problem is detected within a day.
  * Docker doesn't restart unhealthy containers on its own, and the error is often only recoverable by restarting both signal-cli-rest-api and signalblast. Install the [watchdog](https://github.com/Gara-Dorta/signalblast/blob/main/docker/watchdog.sh) as a systemd user timer that does that, it runs as your user (which must be able to run docker):
    ```bash
    curl -fsSL https://raw.githubusercontent.com/Gara-Dorta/signalblast/main/docker/install_watchdog.sh | bash
    ```
  * Uninstall it with:
    ```bash
    curl -fsSL https://raw.githubusercontent.com/Gara-Dorta/signalblast/main/docker/install_watchdog.sh | bash -s -- --uninstall
    ```
  * Alternatively, Docker Swarm and Podman (`--health-on-failure=restart`) can restart the signalblast container natively, but they won't restart signal-cli-rest-api.

### Option 2: python environment

* Set up signal-cli-rest-api as specified [here](https://signalbot-org.github.io/signalbot/latest/getting_started/#setup-signal-cli-rest-api).
* Install signalblast in a new virtual environment, [uv](https://docs.astral.sh/uv/) is recommended
  ```bash
  uv tool install signalblast
  ```
* Set the [configuration](#configuration) as environment variables or in a `.env` file in the folder you run it from, then run it with
  ```bash
  signalblast
  ```

## Configuration

signalblast reads its settings from environment variables, or from a `.env` file in the working directory. Empty values are treated as unset.

| Variable | Default | Description |
|---|---|---|
| `SIGNALBLAST_PHONE_NUMBER` | required | The phone number of the bot |
| `SIGNALBLAST_PASSWORD` | | The password to become an admin. It is stored hashed, so it only needs to be set on the first start or to change it. Without it nobody can become an admin |
| `SIGNALBLAST_SIGNAL_SERVICE` | `localhost:8080` | The address of signal-cli-rest-api |
| `SIGNALBLAST_DATA_DIR` | `~/.local/share/signalblast` | Where the database is stored |
| `SIGNALBLAST_WELCOME_MESSAGE` | `Subscription successful!` | The reply to `!subscribe` |
| `SIGNALBLAST_INSTRUCTIONS_URL` | | A link with instructions, shown in the help |
| `SIGNALBLAST_EXPIRATION_TIME` | 4 weeks | The disappearing messages timer of the chats with the subscribers in seconds, `0` disables it |
| `SIGNALBLAST_HEALTHCHECK_RECEIVER` | | The contact or group that receives the health check pings, the health check is disabled without it |
| `SIGNALBLAST_HEALTHCHECK_PORT` | `15556` | The port of the health check endpoint, on localhost |
| `SIGNALBLAST_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR` |
| `SIGNALBLAST_LOG_FILE` | | Log to this file, rotated weekly, instead of the console |

## Upgrading

The database is created, and upgraded, automatically on start. Data from versions that stored it in `subscribers.csv`, `banned_users.csv` and `admin.txt` is imported into the database the first time, and the files are renamed to `*.migrated`. You can delete them once the bot works as expected.

See the [changelog](CHANGELOG.md) for the changes to the commands and the configuration.

## Development

* Set up signal-cli-rest-api as specified in the [installation](#installation) section.
* Clone the repo
* Install [uv](https://docs.astral.sh/uv/)
* Install the repo and the dependencies in a new virtual environment with `uv sync`
* Install the prek hooks with `uv run prek install`, they run ruff and ty
* Run the tests with `uv run pytest`
* Run the bot
  * Directly via `uv run signalblast`
  * Via systemd as a user service with `systemd/signalblast.service`, see the comments in the file for how to install it. Create `systemd/env_file.env` from `systemd/env_file.env.example` for the configuration.
* Optional: install signalbot as an editable dependency with `uv add --editable ../signalbot/`, but don't commit that change

### Docker compose

`docker/compose_build.sh` and `docker/compose_up.sh` build and run the image from the local code.
