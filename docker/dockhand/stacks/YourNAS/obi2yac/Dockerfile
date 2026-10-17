FROM python:3.12-slim

ARG OBI2YAC_REF=master

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 \
    --branch "${OBI2YAC_REF}" \
    https://github.com/TheSmee/obi2yac.git /app/obi2yac

WORKDIR /app

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "obi2yac"]
