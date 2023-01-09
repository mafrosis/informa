FROM python:3.10-slim AS builder

WORKDIR /src

RUN pip install wheel

# Fetch/build wheels for dependencies
COPY pyproject.toml /src
COPY informa /src/informa

# Build application wheel
RUN python -m pip wheel --no-cache-dir --wheel-dir /dist .

# ---

FROM python:3.10-slim

WORKDIR /src

# Copy in the built wheels
COPY --from=builder /dist /dist

# Install
RUN python -m pip install --no-index --find-links=/dist --no-cache informa

ENTRYPOINT ["informa"]
CMD ["start"]
