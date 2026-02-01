FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

# Install curl for the healthcheck
RUN apt-get update && \
    apt-get install -y curl=7.* --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

##########################
# Create non-root user
##########################
RUN useradd --create-home --shell /bin/bash --uid 1000 user
USER user
WORKDIR /home/user

ARG SIGNALBLAST_VERSION

###########################
# Install from source dist
###########################
# COPY dist/signalblast-$SIGNALBLAST_VERSION.tar.gz /tmp/signalblast-$SIGNALBLAST_VERSION.tar.gz

# RUN tar -xzf /tmp/signalblast-$SIGNALBLAST_VERSION.tar.gz && \
#     uv venv && \
#     uv pip install --no-cache-dir /tmp/signalblast-$SIGNALBLAST_VERSION.tar.gz

###########################
# Install from wheel
###########################
COPY dist/signalblast-$SIGNALBLAST_VERSION-py3-none-any.whl /tmp/signalblast-$SIGNALBLAST_VERSION-py3-none-any.whl
RUN uv venv && \
    uv pip install --no-cache-dir /tmp/signalblast-$SIGNALBLAST_VERSION-py3-none-any.whl

###########################
ENV SIGNALBLAST_CONFIG_DIR=/home/user/.local/share/signalblast

ENTRYPOINT ["uv", "run", "python", "-m", "signalblast.main"]

HEALTHCHECK --interval=8h --start-period=30s --retries=3 CMD curl -f http://localhost:15556 || exit 1
