# The images are pinned by digest so that builds are reproducible, dependabot keeps them up to date

###########################
# Build the wheel
###########################
FROM python:3.14.8-slim-trixie@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170 AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.14@sha256:1025398289b62de8269e70c45b91ffa37c373f38118d7da036fb8bb8efc85d97 /uv /bin/

# The git metadata is not in the build context, so hatch-vcs takes the version from here
ARG SIGNALBLAST_VERSION
ENV SETUPTOOLS_SCM_PRETEND_VERSION=$SIGNALBLAST_VERSION
# Commit timestamp, used instead of the current time so that the build is reproducible
ARG SOURCE_DATE_EPOCH

WORKDIR /build
COPY pyproject.toml uv.lock build-constraints.txt README.md LICENSE ./
COPY src ./src
# The dependencies are exported from uv.lock with their hashes, so the image gets the same versions as the lock file
RUN uv build --wheel --build-constraint build-constraints.txt --require-hashes --out-dir /build/dist && \
    uv export --locked --no-dev --no-emit-project --output-file /build/dist/requirements.txt

###########################
# Final image
###########################
FROM python:3.14.8-slim-trixie@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170

# useradd writes the current date to /etc/shadow, and pip the source timestamps to the .pyc files, unless this is set
ARG SOURCE_DATE_EPOCH

##########################
# Create non-root user
##########################
# --no-log-init avoids writing to lastlog and faillog
RUN useradd --create-home --no-log-init --shell /bin/bash --uid 1000 user
USER 1000
WORKDIR /home/user

###########################
# Install from wheel
###########################
COPY --from=builder /build/dist/ /tmp/dist/
RUN python -m venv .venv && \
    .venv/bin/pip install --no-cache-dir --disable-pip-version-check --require-hashes --requirement /tmp/dist/requirements.txt && \
    .venv/bin/pip install --no-cache-dir --disable-pip-version-check --no-deps /tmp/dist/*.whl

###########################
ENV SIGNALBLAST_DATA_DIR=/home/user/.local/share/signalblast

ENTRYPOINT ["/home/user/.venv/bin/signalblast"]

HEALTHCHECK --interval=8h --timeout=90s --start-period=1m --retries=3 CMD ["sh", "-c", "[ -z \"$SIGNALBLAST_HEALTHCHECK_RECEIVER\" ] || python -c \"import urllib.request; urllib.request.urlopen('http://localhost:${SIGNALBLAST_HEALTHCHECK_PORT:-15556}', timeout=60)\""]
