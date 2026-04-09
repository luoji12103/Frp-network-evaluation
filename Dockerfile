FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

ARG MC_NETPROBE_RELEASE_VERSION=1.0
ARG MC_NETPROBE_BUILD_REF=unknown

ENV MC_NETPROBE_RELEASE_VERSION=${MC_NETPROBE_RELEASE_VERSION} \
    MC_NETPROBE_BUILD_REF=${MC_NETPROBE_BUILD_REF}

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        iperf3 \
        iputils-ping \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash app

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY . .

RUN mkdir -p /app/config/agent /app/results /app/logs /app/data \
    && chown -R app:app /app

USER root

EXPOSE 8765

ENTRYPOINT ["bash", "docker/entrypoint-webui.sh"]
