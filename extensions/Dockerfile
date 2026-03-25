FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps for DuckDB/Arrow wheels + git for possible pulls
RUN apt-get update \
  && apt-get install -y --no-install-recommends curl ca-certificates git \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy extensions project
COPY extensions/ /app/extensions/

# Install extensions + Prefect extra into system Python
RUN pip install --no-cache-dir -e "/app/extensions[prefect]"

# Default; Prefect worker will override command
CMD ["bash", "-lc", "python -V && prefect version"]
