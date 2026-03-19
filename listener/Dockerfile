# ================================
# Base stage
# ================================

FROM python:3.12-slim AS base

WORKDIR /app

# Install dependencies first (better layer caching)

# install build tools for fastlogging
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

COPY listener/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ /app/shared/
RUN pip install --no-cache-dir -r /app/shared/requirements.txt

COPY listener/. .
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# ================================
# Test stage
# ================================
FROM base AS test

RUN pip install --no-cache-dir pytest

RUN pytest tests/ -v

# ================================
# Production stage
# ================================
FROM base AS production

CMD ["python", "listener_management.py"]
