FROM python:3.12-slim AS builder

WORKDIR /src

RUN apt update && apt install -y git

RUN pip install wheel

# Fetch/build wheels for dependencies
COPY pyproject.toml /src
COPY informa /src/informa

# Build application wheel
RUN python -m pip wheel --no-cache-dir --wheel-dir /dist .

# ---

FROM python:3.12-slim

WORKDIR /src

RUN apt update && apt install -y curl git

# Copy in the built wheels
COPY --from=builder /dist /dist

# Install
RUN python -m pip install --no-index --find-links=/dist --no-cache informa

ENTRYPOINT ["informa"]
CMD ["start"]
