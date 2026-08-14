# Production Dockerfile for Telegram Bot Platform using uv
FROM python:3.11-slim

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency configs
COPY pyproject.toml README.md .env.example ./

# Copy source code
COPY platform_core ./platform_core
COPY bots ./bots

# Install dependencies using uv
RUN uv venv .venv && \
    . .venv/bin/activate && \
    uv pip install -e .

ENV PATH="/app/.venv/bin:$PATH"

# Default entry point runs image bot in mock mode unless overridden
CMD ["python", "-m", "platform_core.cli", "start", "all"]
