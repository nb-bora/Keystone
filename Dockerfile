# Multi-stage Dockerfile pour Aegis IAM Enterprise API
# Stage 1: Build & Environment Setup
FROM python:3.11-slim as builder

WORKDIR /build

# Désactiver l'écriture de fichiers .pyc et forcer stdout non-bufferisé
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir --prefix=/install . fastapi pydantic uvicorn

# Stage 2: Final Runtime Image (Secured & Non-root)
FROM python:3.11-slim as runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

# Création d'un utilisateur système non-privilégié (Sécurité Docker Best-Practice)
RUN groupadd -g 10001 aegisgroup && \
    useradd -u 10001 -g aegisgroup -s /bin/sh -m aegisuser

COPY --from=builder /install /usr/local
COPY --from=builder /build/src /app/src
COPY README.md /app/

RUN chown -R aegisuser:aegisgroup /app

USER aegisuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "aegis.drivers.fastapi.app:app", "--host", "0.0.0.0", "--port", "8000"]
