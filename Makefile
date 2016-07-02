.PHONY: dependencies setup build run

PROJECT?=informa
BUILD_TAG?=dev
FORCE?=


gunicorn: dependencies
	salt-call -c config/ state.apply app.source,gunicorn,informa

build:
	@docker build $(FORCE) \
		--build-arg BUILD_TAG=$(BUILD_TAG) \
		--tag mafrosis/informa:$(BUILD_TAG) \
		-f config/Dockerfile .

run:
ifeq ($(BUILD_TAG), dev)
	python manage.py runserver --host 0.0.0.0 --port 8003
else
	python manage.py runserver --host 0.0.0.0 --port 8003
endif

run-celery-worker:
	C_FORCE_ROOT=1 celery worker -A manage.celery -l warning --workdir=/srv/app --purge
