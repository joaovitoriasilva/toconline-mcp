FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (cache layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source code
COPY src/ src/
RUN uv sync --frozen --no-dev

EXPOSE 8000
ENTRYPOINT ["uv", "run", "toconline-mcp"]
