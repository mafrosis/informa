FROM python:3.12-slim AS builder

WORKDIR /src

RUN pip install wheel

# Fetch/build wheels for dependencies
COPY pyproject.toml /src
COPY informa /src/informa

# Build application wheel
RUN python -m pip wheel --no-cache-dir --wheel-dir /dist .

# ---

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
	curl \
	gnupg \
	xvfb \
	&& rm -rf /var/lib/apt/lists/*

WORKDIR /src

# Copy in the built wheels
COPY --from=builder /dist /dist

COPY transto /src/transto
RUN pip install -e /src/transto
COPY gmsa /src/gmsa
RUN pip install -e /src/gmsa

# Install
RUN python -m pip install --no-cache-dir --no-index --find-links=/dist --no-cache informa

# Playwright for kindle-gcal
RUN playwright install --with-deps chromium

COPY ./templates /src/templates

ENTRYPOINT ["informa"]
CMD ["start"]
