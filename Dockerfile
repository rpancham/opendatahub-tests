FROM python:3.13

ARG USER=odh
ARG HOME=/home/$USER
ARG TESTS_DIR=$HOME/opendatahub-tests/
ENV UV_PYTHON=python3.13
ENV UV_COMPILE_BYTECODE=1
ENV UV_NO_SYNC=1
ENV UV_NO_CACHE=1

ENV BIN_DIR="$HOME_DIR/.local/bin"
ENV PATH="$PATH:$BIN_DIR"

RUN apt-get update \
    && apt-get install -y ssh gnupg software-properties-common curl gpg wget vim apache2-utils rsync\
    && apt-get clean autoclean \
    && apt-get autoremove --yes \
    && rm -rf /var/lib/{apt,dpkg,cache,log}/

# Install grpcurl
RUN curl -sSL "https://github.com/fullstorydev/grpcurl/releases/download/v1.9.2/grpcurl_1.9.2_linux_x86_64.tar.gz"  --output /tmp/grpcurl_1.2.tar.gz \
    && tar xvf /tmp/grpcurl_1.2.tar.gz --no-same-owner \
    && mv grpcurl /usr/bin/grpcurl


RUN useradd -ms /bin/bash $USER
USER $USER
WORKDIR $HOME_DIR
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx ${BIN_DIR}/

WORKDIR $TESTS_DIR
COPY --chown=$USER:$USER . $TESTS_DIR

RUN uv sync

ENTRYPOINT ["uv", "run", "pytest"]
