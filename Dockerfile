FROM python:3.8-slim

RUN apt-get update && apt-get install build-essential -y

WORKDIR /usr/src/app

COPY ./docker_run.sh /docker_run.sh
COPY ./pyproject.toml /usr/src/app/pyproject.toml

RUN python -m pip install poetry && \
    python -m poetry install && \
    chmod +x /docker_run.sh && \
    mkdir /data

VOLUME /data

COPY . .

CMD ["/docker_run.sh"]
