FROM python:3.11-slim

# Minimal OS deps and consistent certs
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl \
  && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # pass a token at runtime if you have one
    GITHUB_TOKEN=""

WORKDIR /app

# Install Python deps first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY main.py ./main.py

# Create and use an unprivileged user
RUN useradd -m appuser
USER appuser

# No port to expose. MCP stdio server speaks over stdin/stdout.
CMD ["python", "main.py"]
