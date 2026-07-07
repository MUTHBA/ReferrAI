# -----------------------------------------------------------------------------
# backend/Dockerfile
#
# Multi-layer image for the FastAPI backend on Python 3.13-slim. requirements.txt
# and requirements-ml.txt are installed before source code so the pip layer is
# cache-hit on code-only changes. requirements-ml.txt (scikit-learn, joblib,
# sentence-transformers, shap) is required by the AI scoring pipeline — it was
# previously excluded but must now be included since AI features are live.
# alembic upgrade head runs at container start (before uvicorn) so the DB schema
# is always current before the API accepts requests.
# For production: replace CMD with `uvicorn app.main:app --host 0.0.0.0 --port
# 8000 --workers 4` and add a separate migration step to CI/CD.
# -----------------------------------------------------------------------------

FROM python:3.13-slim

WORKDIR /app

# System deps: curl (health-check), libpq (psycopg2 runtime)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages first (cached unless requirements files change).
# requirements-ml.txt contains heavy AI/ML dependencies (scikit-learn, joblib,
# sentence-transformers, shap) required by the AI scoring pipeline.
COPY requirements.txt requirements-ml.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-ml.txt

# Copy source — overridden by bind-mount in development
COPY . .

EXPOSE 8000

# Run DB migrations then start with hot-reload.
# In production replace with: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
