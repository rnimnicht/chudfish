# ================================
# Base stage
# ================================

FROM python:3.12-slim AS base

WORKDIR /app

# Install dependencies first (better layer caching)
COPY listener/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ /app/shared/
RUN pip install --no-cache-dir -r /app/shared/requirements.txt

COPY listener/listener.py .
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# ================================
# Test stage
# ================================
FROM base AS test

RUN pip install --no-cache-dir pytest

COPY listener/tests/ tests/

RUN pytest tests/ -v

# ================================
# Production stage
# ================================
FROM test AS production

CMD ["python", "listener.py"]
