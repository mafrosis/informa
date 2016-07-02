FROM python:3.4-slim

ARG BUILD_TAG=dev
ENV BUILD_TAG=$BUILD_TAG

RUN apt-get update && apt-get -y install \
	build-essential \
	git \
	memcached \
	sqlite3

WORKDIR /srv/app

COPY config /srv/app/config

RUN pip3 install -r config/requirements-dev.txt

EXPOSE 80

CMD ["bash"]
