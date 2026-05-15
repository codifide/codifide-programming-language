FROM python:3.11-slim

# Install build tools for any native extensions (none currently, but
# keeps the image forward-compatible).
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the package first so Docker layer caching works — dependencies
# change less often than source code.
COPY pyproject.toml ./
COPY codifide/ ./codifide/

# Install the package in editable mode so the CLI entry point works.
RUN pip install --no-cache-dir -e .

# The symbol store lives on a persistent volume mounted at /data/store.
# This path is set via the CODIFIDE_STORE environment variable.
ENV CODIFIDE_STORE=/data/store

# Expose the RPC API port.
EXPOSE 7777

# Health check — the /health endpoint returns 200 with no store access.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:7777/health')" || exit 1

# Start the server in read-only mode for the public registry.
# --host 0.0.0.0 is required inside a container; the fly.toml
# internal_port matches this.
CMD ["python3", "-m", "codifide", "serve", \
     "--host", "0.0.0.0", \
     "--port", "7777", \
     "--read-only"]
