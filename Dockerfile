FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (cache layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source code and README (required by pyproject.toml build metadata)
COPY README.md .
COPY src/ src/
RUN uv sync --frozen --no-dev

ENTRYPOINT ["uv", "run", "toconline-mcp"]
