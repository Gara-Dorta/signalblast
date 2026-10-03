# Changelog

## Unreleased

This release moves to signalbot 2 and a sqlite database, and changes how admins moderate the list so that they never see who the subscribers are.

### Breaking changes

* **Configuration** is read from `SIGNALBLAST_*` environment variables, or a `.env` file, only. The command line flags are gone.
  * `SIGNAL_SERVICE` is now `SIGNALBLAST_SIGNAL_SERVICE`.
  * `SIGNALBLAST_CONFIG_DIR` is now `SIGNALBLAST_DATA_DIR`.
  * Run the bot with the `signalblast` command (`python -m signalblast.main` still works).
* **Admins**
  * There can be several admins. `!add admin <password>` adds an admin instead of replacing the current one, and `!remove admin` takes the id of the admin to remove: `!remove admin <password> <admin id>`.
  * `!ban` and `!lift ban` no longer take user ids. Quote a broadcast or a message from a user and send `!ban`; lift bans by number with `!lift ban <number>`, see `!list bans`.
  * `!reply <user id>` is gone. Messages from users arrive as `User wrote: …`; quote them to reply. Users answer by quoting the reply, and every message of the conversation quotes the one it answers.
  * `!last msg user uuid` is gone.
  * `!set ping` and `!unset ping` are gone, use the health check (`SIGNALBLAST_HEALTHCHECK_RECEIVER`) instead.
* **Data** is stored in a sqlite database, `signalblast.db` in the data folder. The `subscribers.csv`, `banned_users.csv` and `admin.txt` files from older versions are imported automatically on the first start and renamed to `*.migrated`.
* **Docker**
  * signal-cli-rest-api is only reachable from the host (`127.0.0.1:8080`), and its data folder is no longer mounted into the signalblast container.
  * signal-cli-rest-api is pinned to a version instead of using `latest`, set `SIGNAL_CLI_REST_API_VERSION` in `.env` to change it.
  * Images are only published for releases.
  * The `autoheal` container is replaced by an optional systemd watchdog, see the README.

### New

* `!list admins`, `!list bans`.
* `SIGNALBLAST_LOG_LEVEL` and `SIGNALBLAST_LOG_FILE`.
* `SIGNALBLAST_EXPIRATION_TIME=0` disables disappearing messages.

### Fixes

* The bot froze after a subscriber edited or deleted a message that wasn't a broadcast.
* Mistyped or capitalised commands, e.g. `!Unsubscribe`, were broadcast to everyone. Commands are now case insensitive, and unknown commands get the help.
* A `!broadcast` in the middle of a message was removed from it.
* Edits of a broadcast now also reach subscribers who joined after it was sent, and later edits and deletes reach them too.
* Subscribers who can't receive messages are removed after 10 failed broadcasts in a row, also across restarts.
* The typing indicator kept being sent forever after a broadcast failed.
* Attachments are deleted from signal-cli after every message, not only after broadcasts.
* `!add admin` crashed when no admin password was set, and checking passwords blocked the bot.
* Log files were rotated by several handlers at once.
* The health check could reset the connection instead of answering.
