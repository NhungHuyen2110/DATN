FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HOME=/models
WORKDIR /srv/AI
COPY AI/requirements-test.txt AI/requirements-runtime.txt /tmp/
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install --no-cache-dir -r /tmp/requirements-runtime.txt \
    && useradd --uid 10001 --create-home app
# Match the AI runtime prefix so BuildKit can reuse its tested CPU/model layer.
# Backend-only changes no longer invalidate the expensive embedding install.
WORKDIR /srv
ENV LUMIERE_LOAD_DOTENV=false
COPY backend/requirements.txt /tmp/backend-requirements.txt
RUN pip install --no-cache-dir -r /tmp/backend-requirements.txt
COPY AI/ /srv/AI/
COPY backend/ /srv/backend/
COPY shared/ /srv/shared/
COPY scripts/run_index_worker.py /srv/scripts/run_index_worker.py
ARG LUMIERE_GIT_COMMIT=unknown
ARG LUMIERE_SOURCE_SHA256=unknown
LABEL org.opencontainers.image.revision=$LUMIERE_GIT_COMMIT io.lumiere.source.sha256=$LUMIERE_SOURCE_SHA256
USER 10001
CMD ["python", "-B", "scripts/run_index_worker.py", "--environment", "test", "--confirm-isolated", "--backup-reference", "/recovery/backup-reference.json", "--reconcile", "--watch"]
