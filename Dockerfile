ARG PLAYWRIGHT_VERSION=v1.55.0

# --- Stage 1: Build Wheels ---
FROM python:3.12-slim AS builder

WORKDIR /src

# Install essential build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
	git \
	&& rm -rf /var/lib/apt/lists/*

# Install pip build dependencies into the main environment (required for --no-build-isolation)
RUN pip install hatchling wheel setuptools

# Copy source code and build config
COPY pyproject.toml /src
COPY informa /src/informa

# Build application wheel.
RUN python -m pip wheel --no-cache-dir --wheel-dir /dist . --no-build-isolation


# --- Stage 2: Minimal Runtime Environment ---
# Make Playwright available via baseimage
FROM mcr.microsoft.com/playwright/python:${PLAYWRIGHT_VERSION}-noble

# Install necessary runtime utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
	curl \
	gnupg \
	xvfb \
	&& rm -rf /var/lib/apt/lists/*

WORKDIR /src

# Copy in the built wheels
COPY --from=builder /dist /dist

# Install everything in /dist using the --no-deps flag
RUN python -m pip install --no-cache-dir --no-index --find-links=/dist --only-binary :all: --no-deps /dist/*

COPY ./templates /src/templates

ENTRYPOINT ["informa"]
CMD ["start"]
