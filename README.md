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

* Subscribers don't see who else is subscribed, or who sent a broadcast.
* Admins don't see who the subscribers are either.
Messages to the admins arrive from `User`, and admins answer and ban people by replying to their messages, never by name or number.
* The bot doesn't store the content of messages.
Its database only remembers who sent what, and only for as long as it needs to:
  * the sender of each broadcast, for 24 hours, so that broadcasts can be edited and deleted
  * the user that each message between a user and the admins belongs to, for 7 days, so that replies reach the right person

Every message passes through the server that hosts the bot, so whoever runs it could, in principle, see who everyone is and what they send.
The bot doesn't record this, but there is no easy way yet to prove from the outside that the host runs an unmodified bot.
If you can get access to the server, you can check that it runs an unmodified, signed release, see [verify the container](#verify-the-container).
Notet that there are attacks that verify ca not rule out, they are listed there.

## Installation

### Option 1: docker compose (recommended)

This uses the images from https://hub.docker.com/r/eradorta/signalblast

1. Set up signal-cli-rest-api as specified [here](https://signalbot-org.github.io/signalbot/latest/01_getting_started/#setup-signal-cli-rest-api).
2. Run the [installer](https://github.com/Gara-Dorta/signalblast/blob/main/install.sh):
   ```bash
   curl -fsSL https://github.com/Gara-Dorta/signalblast/releases/latest/download/install.sh | bash
   ```
   It downloads the `docker-compose.yaml` and the `.env` with the [configuration](#configuration) to `~/.config/signalblast` by default, removes the signal-cli-rest-api container from step 1 and starts signalblast.

To update, or to apply changes to the settings in `~/.config/signalblast/.env`, run the installer again, the settings are kept.

To uninstall, run:
```bash
curl -fsSL https://github.com/Gara-Dorta/signalblast/releases/latest/download/install.sh | bash -s -- --uninstall
```
It removes the containers, the images and the watchdog, and asks whether to also remove the settings, the database and the Signal account of the bot.

### Option 2: python environment

* Set up signal-cli-rest-api as specified [here](https://signalbot-org.github.io/signalbot/latest/01_getting_started/#setup-signal-cli-rest-api).
* Install signalblast in a new virtual environment, [uv](https://docs.astral.sh/uv/) is recommended
  ```bash
  uv tool install signalblast
  ```
* Set the [configuration](#configuration) as environment variables or in a `.env` file in the folder you run it from, then run it with
  ```bash
  signalblast
  ```

### Option 3: docker compose (manual)

This does the same as the installer of option 1, step by step.

* Set up signal-cli-rest-api as specified [here](https://signalbot-org.github.io/signalbot/latest/01_getting_started/#setup-signal-cli-rest-api).
* Stop and remove the `signal-cli-rest-api` container.
* Download the [docker-compose.yaml](https://github.com/Gara-Dorta/signalblast/releases/latest/download/docker-compose.yaml) and [env.example](https://github.com/Gara-Dorta/signalblast/releases/latest/download/env.example) files of the [latest release](https://github.com/Gara-Dorta/signalblast/releases/latest), the latter as `.env`.
  ```bash
  curl -fsSLO https://github.com/Gara-Dorta/signalblast/releases/latest/download/docker-compose.yaml
  curl -fsSL -o .env https://github.com/Gara-Dorta/signalblast/releases/latest/download/env.example
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
  docker compose up -d
  ```
* Optional: restart the containers automatically when signalblast can't send messages.
  * Set `SIGNALBLAST_HEALTHCHECK_RECEIVER` in your `.env` file, it will receive a "Ping" message every 8 hours.
  The signalblast container is reported as unhealthy after 3 failed pings in a row, so a problem is detected within a day.
  * Docker doesn't restart unhealthy containers on its own, and the error is often only recoverable by restarting both signal-cli-rest-api and signalblast. Install the [watchdog](https://github.com/Gara-Dorta/signalblast/blob/main/docker/watchdog.sh) as a systemd user timer that does that, it runs as your user (which must be able to run docker):
    ```bash
    curl -fsSL https://github.com/Gara-Dorta/signalblast/releases/latest/download/install_watchdog.sh | bash
    ```
  * Uninstall it with:
    ```bash
    curl -fsSL https://github.com/Gara-Dorta/signalblast/releases/latest/download/install_watchdog.sh | bash -s -- --uninstall
    ```
  * Alternatively, Docker Swarm and Podman (`--health-on-failure=restart`) can restart the signalblast container natively, but they won't restart signal-cli-rest-api.
* To update, download the `docker-compose.yaml` of the latest release and pull the images.
  ```bash
  curl -fsSLO https://github.com/Gara-Dorta/signalblast/releases/latest/download/docker-compose.yaml
  docker compose pull
  docker compose up -d
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
| `SIGNALBLAST_SIGNAL_SERVICE` | `signal-cli-rest-api:8080` | The address of signal-cli-rest-api |
| `SIGNALBLAST_DATA_DIR` | `~/.local/share/signalblast` | Where the database is stored |
| `SIGNALBLAST_INSTRUCTIONS_URL` | | A link with instructions, shown in the help |
| `SIGNALBLAST_EXPIRATION_TIME` | 4 weeks | The disappearing messages timer of the chats with the subscribers in seconds, `0` leaves the timer of the chats unchanged, `-1` disables it |
| `SIGNALBLAST_HEALTHCHECK_RECEIVER` | | The contact or group that receives the health check pings, the health check is disabled without it |
| `SIGNALBLAST_HEALTHCHECK_PORT` | `15556` | The port of the health check endpoint, on localhost |
| `SIGNALBLAST_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR` |
| `SIGNALBLAST_LOG_FILE` | | Log to this file, rotated weekly, instead of the console |


## Reproducible builds

The PyPI wheel and the docker image are reproducible and they are also signed.
Release tags are signed with the SSH key in [.github/allowed_signers](.github/allowed_signers).

To check that a release on PyPI and Docker Hub was built from the code in its git tag, rebuild and compare it, and check its signatures, with:
```bash
scripts/verify-release.sh v1.2.3
```
Only the image for the platform of your machine is built and checked for reprocibility.
Add `--all-platforms` to rebuild all of them, which needs QEMU.
Add `--signatures-only` to only check the signatures, which is much faster as nothing is built.

For convinience, each github release also has the hashes of the PyPI files in `SHA256SUMS` and the digests of the docker image in `IMAGE-DIGESTS`.

## Verify the container

The checks below make tampering harder and easier to spot but not impossible.
Most importantly, they only show what the containers run when the checks run, a host could run modified containers in between checks.

To verify the containers, run:
```bash
scripts/verify-container.sh
```
It checks that:
* the signalblast image is a signed release.
* signalblast talks to the signal-cli-rest-api specified in the `docker-compose.yaml`.
* the signal-cli-rest-api image is the one pinned in the `docker-compose.yaml`.
  This image is not signed, so this only shows that it is the image published on Docker Hub.
* both containers run their image unmodified:
    * with its command and health check.
    * with only the variables and mounts of their services in that `docker-compose.yaml` added, and `/tmp`.
    * with no files changed outside `/tmp`.
* the Signal account of the bot has no linked devices, as they would receive every message.

Run with `--rebuild` to also run `scripts/verify-release.sh` ([(reproducibility checks](#reproducible-builds)) for that release.

The `verify-container.sh` script will find the default container and version.
Additionaly, it also supports checking against different container names and versions, e.g. `scripts/verify-container.sh my-other-container v1.2.3`.
