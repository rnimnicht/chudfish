# ================================
# Base stage
# ================================

FROM python:3.12-slim AS base

WORKDIR /app

# Install dependencies first (better layer caching)
COPY flask/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ /app/shared/
RUN pip install --no-cache-dir -r /app/shared/requirements.txt

COPY flask/app.py .
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py
ENV PYTHONPATH=/app

# ================================
# Test stage
# ================================
FROM base AS test

RUN pip install --no-cache-dir pytest

COPY flask/tests/ tests/

RUN pytest tests/ -v

# ================================
# Production stage
# ================================
FROM test AS production

EXPOSE 5001

CMD ["flask", "run", "--host=0.0.0.0", "--port=5001"]
