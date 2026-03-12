# ================================
# Base stage
# ================================
FROM python:3.12-slim AS base

WORKDIR /app

# Install dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared module and app code
# COPY shared/ /app/shared/
# COPY flask/ /app/

ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py

# ================================
# Test stage
# ================================
# FROM base AS test

# RUN pip install --no-cache-dir pytest pytest-asyncio

# RUN pytest tests/ -v

# ================================
# Production stage
# ================================
FROM base AS production

COPY app.py .

EXPOSE 5001

CMD ["flask", "run", "--host=0.0.0.0", "--port=5001"]
