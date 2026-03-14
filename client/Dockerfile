# ================================
# Base stage
# ================================

FROM python:3.12-slim AS base

WORKDIR /app

# Install dependencies first (better layer caching)
COPY client/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ /app/shared/
RUN pip install --no-cache-dir -r /app/shared/requirements.txt

COPY client/ .
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

EXPOSE 5001

CMD ["uvicorn", "main:app", "--host=0.0.0.0", "--port=5001"]
