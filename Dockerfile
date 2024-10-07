# The builder image, used to build the virtual environment
FROM python:3.10 AS base

RUN useradd --create-home --shell /bin/bash --uid 1000 user
USER user
RUN mkdir -p /home/user/signalblast
WORKDIR /home/user/signalblast

ARG SIGNALBLAST_VERSION

RUN pip install --no-cache-dir git+https://github.com/Era-Dorta/signalbot.git@broadcastbot --no-deps && \
    pip install --no-cache-dir signalblast==$SIGNALBLAST_VERSION

ENTRYPOINT ["python", "-m", "signalblast.main"]

# The dev image, used for development
FROM base AS dev

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# COPY pyproject.toml uv.lock ./

# RUN uv sync
