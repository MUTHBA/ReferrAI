# -----------------------------------------------------------------------------
# backend/Dockerfile
#
# FastAPI backend on Python 3.13-slim, including the AI/ML stack.
#  * Dependencies are installed before the source so code-only changes reuse
#    the cached pip layer. The optional embedding stack uses CPU-only torch
#    (a few hundred MB instead of several GB with CUDA).
#  * The sentence-transformers model used by partner discovery is downloaded
#    at build time into HF_HOME, and HF_HUB_OFFLINE=1 stops runtime downloads.
#  * Trained model files live in AI_MODEL_DIR (/models), a Docker volume, so
#    they survive rebuilds. On start the container runs migrations, trains the
#    models if none exist yet (~20s), then starts uvicorn.
#  * build-essential is installed so shap's g++ extension compiles (merged from the
#    week-11 hardening work; do not remove).
# Production (docker-compose.prod.yml) overrides the command: 4 workers, no reload.
# -----------------------------------------------------------------------------

FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/hf-cache \
    AI_MODEL_DIR=/models

# curl: health check. libgomp1: OpenMP runtime used by scikit-learn/torch.
# build-essential: g++ to compile shap's native _cext extension if no wheel fits.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl libgomp1 build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-ml.txt requirements-embeddings.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-ml.txt

# Optional semantic embeddings for partner discovery (CPU-only torch). Set
# --build-arg INSTALL_EMBEDDINGS=false to skip; if the download fails the
# build continues and discovery falls back to TF-IDF similarity.
ARG INSTALL_EMBEDDINGS=true
RUN if [ "$INSTALL_EMBEDDINGS" = "true" ]; then \
      ( pip install --no-cache-dir torch==2.7.1 --index-url https://download.pytorch.org/whl/cpu \
        && pip install --no-cache-dir -r requirements-embeddings.txt \
        && python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" ) \
      || echo "WARNING: embeddings not installed - partner discovery will use TF-IDF"; \
    fi
# Never download models at runtime (the model above is baked into HF_HOME).
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

COPY . .
RUN mkdir -p /models

EXPOSE 8000

# --proxy-headers/--forwarded-allow-ips: request.client.host is the real
# visitor IP behind nginx (click tracking and fraud rules depend on it).
CMD ["sh", "-c", "alembic upgrade head && python -m app.ai.train --if-missing && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --proxy-headers --forwarded-allow-ips='*'"]
