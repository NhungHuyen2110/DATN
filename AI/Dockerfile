FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HOME=/models
WORKDIR /srv/AI
COPY AI/requirements-test.txt AI/requirements-runtime.txt /tmp/
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install --no-cache-dir -r /tmp/requirements-runtime.txt \
    && useradd --uid 10001 --create-home app
COPY AI/ /srv/AI/
COPY shared/ /srv/shared/
COPY data/ /srv/data/
COPY output/products_ai.csv /srv/output/products_ai.csv
ARG LUMIERE_GIT_COMMIT=unknown
ARG LUMIERE_SOURCE_SHA256=unknown
LABEL org.opencontainers.image.revision=$LUMIERE_GIT_COMMIT io.lumiere.source.sha256=$LUMIERE_SOURCE_SHA256
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3)"
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
