FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

RUN useradd --create-home --shell /bin/bash --uid 1000 user
USER user
RUN mkdir -p /home/user/signalblast
WORKDIR /home/user/signalblast

ARG SIGNALBLAST_VERSION

COPY dist/signalblast-$SIGNALBLAST_VERSION-py3-none-any.whl signalblast-$SIGNALBLAST_VERSION-py3-none-any.whl

RUN uv venv && uv pip install --no-cache signalblast-$SIGNALBLAST_VERSION-py3-none-any.whl

ENTRYPOINT ["uv", "run", "python", "-m", "signalblast.main"]
