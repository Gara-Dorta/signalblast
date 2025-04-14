FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# Git is needed for the signalbot dependency of the source dist
RUN apt-get update && \
    apt-get install -y git=1:2.* curl=7.* --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash --uid 1000 user
USER user
RUN mkdir -p /home/user/signalblast
WORKDIR /home/user/signalblast

ARG SIGNALBLAST_VERSION

###########################
# Install from source dist
###########################
COPY dist/signalblast-$SIGNALBLAST_VERSION.tar.gz signalblast-$SIGNALBLAST_VERSION.tar.gz

RUN tar -xzf signalblast-$SIGNALBLAST_VERSION.tar.gz

WORKDIR /home/user/signalblast/signalblast-$SIGNALBLAST_VERSION

RUN uv sync --no-dev

###########################
# Install from wheel
###########################
# COPY dist/signalblast-$SIGNALBLAST_VERSION-py3-none-any.whl signalblast-$SIGNALBLAST_VERSION-py3-none-any.whl
# RUN uv venv && uv pip install --no-cache signalblast-$SIGNALBLAST_VERSION-py3-none-any.whl

ENTRYPOINT ["uv", "run", "python", "-m", "signalblast.main"]

HEALTHCHECK --interval=8h --start-period=15s --retries=3 CMD curl -f http://localhost:15556 || exit 1
