# The builder image, used to build the virtual environment
FROM python:3.10 AS base

RUN useradd --create-home --shell /bin/bash --uid 1000 user
USER user
RUN mkdir -p /home/user/signalblast
WORKDIR /home/user/signalblast

# The builder image, used to build the virtual environment
FROM base AS builder

COPY pyproject.toml poetry.lock ./
RUN touch README.md

RUN pip install poetry==1.8.3

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

RUN poetry install --without dev && rm -rf $POETRY_CACHE_DIR

# The runtime image, used to just run the code provided its virtual environment
FROM base AS runtime

ENV VIRTUAL_ENV=/home/user/signalblast/.venv \
    PATH="/home/user/signalblast/.venv/bin:$PATH"

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}

ARG SIGNALBLAST_VERSION

RUN pip install git+https://github.com:Era-Dorta/signalbot.git@broadcastbot --no-deps

RUN pip install --no-deps signalblast==$SIGNALBLAST_VERSION

ENTRYPOINT ["python", "-m", "signalblast.main"]

# The dev image, used for development
FROM base AS dev

COPY pyproject.toml poetry.lock ./
RUN touch README.msd

RUN pip install poetry==1.8.3

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

RUN poetry install
