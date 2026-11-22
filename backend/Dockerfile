# Backend API image. Build from the repository root:
#   docker build -f backend/Dockerfile -t regulationdiff-backend .

FROM python:3.11.11-slim-bookworm AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY shared /src/shared
COPY backend /src/backend
RUN pip install "/src/shared[fastembed]" /src/backend
# Bake the embedding model into the image: offline start-up, repeatable builds.
RUN EMBEDDINGS_MODE=fastembed MODEL_CACHE_DIR=/opt/models python -m regdiff_common.embeddings

FROM python:3.11.11-slim-bookworm
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /data/documents \
    && chown app:app /data/documents
COPY --from=build /opt/venv /opt/venv
COPY --from=build --chown=app:app /opt/models /opt/models
COPY --chmod=755 docker/python-entrypoint.sh /usr/local/bin/entrypoint.sh

ARG BUILD_NUMBER=dev
ARG GIT_COMMIT=local
ARG BUILD_TIME=unknown
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    EMBEDDINGS_MODE=fastembed \
    MODEL_CACHE_DIR=/opt/models \
    HF_HUB_OFFLINE=1 \
    STORAGE_DIR=/data/documents \
    BUILD_NUMBER=$BUILD_NUMBER \
    GIT_COMMIT=$GIT_COMMIT \
    BUILD_TIME=$BUILD_TIME

USER app
WORKDIR /home/app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=30s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
ENTRYPOINT ["entrypoint.sh"]
CMD ["uvicorn", "regdiff_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
