###########################
# Build the wheel
###########################
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

# The git metadata is not in the build context, so hatch-vcs takes the version from here
ARG SIGNALBLAST_VERSION
ENV SETUPTOOLS_SCM_PRETEND_VERSION=$SIGNALBLAST_VERSION

WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN uv build --wheel --out-dir /build/dist

###########################
# Final image
###########################
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

##########################
# Create non-root user
##########################
RUN useradd --create-home --shell /bin/bash --uid 1000 user
USER 1000
WORKDIR /home/user

###########################
# Install from wheel
###########################
COPY --from=builder /build/dist/ /tmp/dist/
RUN uv venv && \
    uv pip install --no-cache-dir /tmp/dist/*.whl

###########################
ENV SIGNALBLAST_DATA_DIR=/home/user/.local/share/signalblast

ENTRYPOINT ["uv", "run", "python", "-m", "signalblast.main"]

HEALTHCHECK --interval=8h --timeout=90s --start-period=1m --retries=3 CMD ["sh", "-c", "[ -z \"$SIGNALBLAST_HEALTHCHECK_RECEIVER\" ] || python -c \"import urllib.request; urllib.request.urlopen('http://localhost:${SIGNALBLAST_HEALTHCHECK_PORT:-15556}', timeout=60)\""]
