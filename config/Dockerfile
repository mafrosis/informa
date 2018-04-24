FROM python:3.5-slim

ARG BUILD_TAG=dev
ENV BUILD_TAG=$BUILD_TAG

RUN apt-get update && \
	apt-get -y --no-install-recommends install \
	build-essential \
	libssl-dev \
	git \
	memcached \
	sqlite3 \
	&& apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/app

COPY config /srv/app/config

RUN pip3 install --pre -r config/requirements-dev.txt

ENV FLASK_APP=entrypoint.py

EXPOSE 80

CMD ["bash"]
