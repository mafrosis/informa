FROM python:3.12-slim AS builder

WORKDIR /src

RUN apt-get update && apt-get install -y --no-install-recommends git

# Install python build backends & wheel
RUN pip install hatchling setuptools wheel

# Fetch/build wheels for dependencies
COPY pyproject.toml /src
COPY informa /src/informa

# Build application wheel
RUN python -m pip wheel --no-cache-dir --no-build-isolation --wheel-dir /dist .

# ---

# Playwright for kindle-gcal
FROM mcr.microsoft.com/playwright/python:v1.55.0-noble

RUN apt-get update && apt-get install -y --no-install-recommends \
	curl \
	gnupg \
	xvfb \
	&& rm -rf /var/lib/apt/lists/*

WORKDIR /src

# Copy in the built wheels
COPY --from=builder /dist /dist

# Install
RUN python -m pip install --no-cache-dir --no-index --find-links=/dist --only-binary :all: --no-deps /dist/*

COPY ./templates /src/templates

ENTRYPOINT ["informa"]
CMD ["start"]
