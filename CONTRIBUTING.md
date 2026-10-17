
# Contributing

Contributions are welcome.

## Development setup

* Set up signal-cli-rest-api as specified in the [installation](README.md#installation) section.
* Clone the repo
* Install [uv](https://docs.astral.sh/uv/)
* Install the repo and the dependencies in a new virtual environment with `uv sync`
* Install the prek hooks with `uv run prek install`, they run `ruff` and `ty`
* Run the tests with `uv run pytest`
* Run `signal-cli-rest-api` with `docker compose -f docker-compose.yaml -f docker/compose.dev.yaml up signal-cli-rest-api` and set `SIGNALBLAST_SIGNAL_SERVICE=localhost:8080` in the `.env` file
* Run the bot `uv run signalblast`
* Optional: install signalbot as an editable dependency with `uv add --editable ../signalbot/`, but don't commit that change
* Maintainers: see [RELEASING.md](RELEASING.md) for how to make a release

### Docker compose

The docker compose scripts will automatically get and set the signalblast version from the git history.
`docker/compose_build.sh` and `docker/compose_up.sh` build and run the image from the local code.
