FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

##########################
# Create non-root user
##########################
RUN useradd --create-home --shell /bin/bash --uid 1000 user
USER 1000
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
ENV SIGNALBLAST_DATA_DIR=/home/user/.local/share/signalblast

ENTRYPOINT ["uv", "run", "python", "-m", "signalblast.main"]

HEALTHCHECK --interval=8h --timeout=90s --start-period=1m --retries=3 CMD ["sh", "-c", "[ -z \"$SIGNALBLAST_HEALTHCHECK_RECEIVER\" ] || python -c \"import urllib.request; urllib.request.urlopen('http://localhost:${SIGNALBLAST_HEALTHCHECK_PORT:-15556}', timeout=60)\""]
