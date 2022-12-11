.PHONY: build
build:
	docker compose build informa

.PHONY: run
run:
	docker compose up --no-build

.PHONY: lint
lint:
	docker compose run --rm --entrypoint=pylint test /src/informa

.PHONY: typecheck
typecheck:
	docker compose run --rm test --mypy /src/informa
