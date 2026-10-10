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
* `!ban` reply `!ban` to a broadcast, or to a message from a user, to ban its sender. This works for broadcasts from the last 24 hours (so the admin must be subscribed to receive them) and for messages from the last 7 days
* `!list bans` show the banned users, numbered, with the start of the message they were banned for
* `!lift ban <number>` lift a ban
* `!version` show the versions of signalblast, signalbot and signal-cli-rest-api

Messages that users send with `!admin` reach every admin as `User wrote: …`. To answer, reply to the message, without any command. The user receives it as `Admin: …` and answers the same way, by replying to it, and so on. The other admins get a copy of every reply. Each message the bot sends in a conversation is a reply to the message it answers, so every chat shows the conversation as a thread. Replying to any message of a conversation continues it, it is never broadcast.

### Privacy

* Subscribers never learn who else is subscribed, or who sent a broadcast.
* Admins never learn who a subscriber is either: users who write to the admins appear as `User`, and bans and answers work by replying to messages.
* The bot's database keeps only:
   * who sent each broadcast, for 24 hours, so that broadcasts can be edited and deleted
   * which user each message between users and admins belongs to, for 7 days, so that replies reach the right person.
   The content of the messages is not stored.
   * both are also used to let admins ban a sender just by replying to their message.
* Whoever hosts the bot can, in principle, see who everyone is and what they send, since every message passes through their server.
By default the bot does not record this.
However, there is currently no easy way to prove that the host has not modified the bot.
Ways to address this are discussed in [#39](https://github.com/Gara-Dorta/signalblast/issues/39).

## Installation

### Option 1: docker compose

This uses the images from https://hub.docker.com/r/eradorta/signalblast

* Install [docker](https://www.docker.com/).
* Set up signal-cli-rest-api for the bot's phone number as specified [here](https://signalbot-org.github.io/signalbot/latest/getting_started/#setup-signal-cli-rest-api).
* Download the [docker-compose.yaml](https://github.com/Gara-Dorta/signalblast/blob/main/docker-compose.yaml) and [.env.example](https://github.com/Gara-Dorta/signalblast/blob/main/.env.example) files, the latter is downloaded as `.env`.
  ```bash
  curl -fsSLO https://raw.githubusercontent.com/Gara-Dorta/signalblast/main/docker-compose.yaml
  curl -fsSL -o .env https://raw.githubusercontent.com/Gara-Dorta/signalblast/main/.env.example
  ```
* Fill in `SIGNALBLAST_PHONE_NUMBER` in `.env`.
The rest are optional, uncomment the ones you want to set, see [configuration](#configuration).
You'll likely want `SIGNALBLAST_PASSWORD`, otherwise nobody can become an admin.
* Create a data folder
  ```bash
  mkdir -p $HOME/.local/share/signalblast
  ```
* Run via docker compose on the folder where the `docker-compose.yaml` file is located:
  ```bash
  docker compose up
  ```
* Optional: restart the containers automatically when signalblast can't send messages.
  * Set `SIGNALBLAST_HEALTHCHECK_RECEIVER` in your `.env` file, it will receive a "Ping" message every 8 hours.
  The signalblast container is reported as unhealthy after 3 failed pings in a row, so a problem is detected within a day.
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

The only required variable is the phone number of the bot:

| Variable | Description |
|---|---|
| `SIGNALBLAST_PHONE_NUMBER` | The phone number of the bot |

The rest are optional:

| Variable | Default | Description |
|---|---|---|
| `SIGNALBLAST_PASSWORD` | | The password to become an admin. It is stored hashed, so it only needs to be set on the first start or to change it. Without it nobody can become an admin |
| `SIGNALBLAST_SIGNAL_SERVICE` | `localhost:8080` | The address of signal-cli-rest-api |
| `SIGNALBLAST_DATA_DIR` | `~/.local/share/signalblast` | Where the database is stored |
| `SIGNALBLAST_INSTRUCTIONS_URL` | | A link with instructions, shown in the help |
| `SIGNALBLAST_EXPIRATION_TIME` | 4 weeks | The disappearing messages timer of the chats with the subscribers in seconds, `0` leaves the timer of the chats unchanged, `-1` disables it |
| `SIGNALBLAST_HEALTHCHECK_RECEIVER` | | The contact or group that receives the health check pings, the health check is disabled without it |
| `SIGNALBLAST_HEALTHCHECK_PORT` | `15556` | The port of the health check endpoint, on localhost |
| `SIGNALBLAST_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR` |
| `SIGNALBLAST_LOG_FILE` | | Log to this file, rotated weekly, instead of the console |

## Development

* Set up signal-cli-rest-api as specified in the [installation](#installation) section.
* Clone the repo
* Install [uv](https://docs.astral.sh/uv/)
* Install the repo and the dependencies in a new virtual environment with `uv sync`
* Install the prek hooks with `uv run prek install`, they run `ruff` and `ty`
* Run the tests with `uv run pytest`
* Run `signal-cli-rest-api` with `docker compose up signal-cli-rest-api`
* Run the bot `uv run signalblast`
* Optional: install signalbot as an editable dependency with `uv add --editable ../signalbot/`, but don't commit that change

### Docker compose

The docker compose scripts will automatically get and set the signalblast version from the git history.
`docker/compose_build.sh` and `docker/compose_up.sh` build and run the image from the local code.

### Reproducible builds

The package distributions and the docker image are reproducible, building the same commit always gives byte-for-byte identical files.
The build tools are pinned (uv in `pyproject.toml`, hatchling in `build-constraints.txt` and the base images by digest in the `Dockerfile`), the image dependencies come from `uv.lock`, and all the timestamps are set from the commit time through `SOURCE_DATE_EPOCH`.

The [Reproducible Builds](.github/workflows/reproducibility.yml) workflow builds everything twice on different runners with `scripts/build-reproducible.sh` and fails if anything differs. It also runs before every release, and the release publishes the distributions it built.

To check that a release on PyPI and Docker Hub was built from the code in its git tag, rebuild and compare it with:
```bash
scripts/verify-release.sh v1.2.3
```
Building the arm64 image needs QEMU, set `PLATFORMS=linux/amd64` to only check the amd64 one.
Update the pinned build backend in `build-constraints.txt` with `scripts/update-build-constraints.sh`, or `scripts/update-build-constraints.sh hatchling` to only upgrade some packages.
