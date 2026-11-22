FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LUMIERE_LOAD_DOTENV=false
WORKDIR /srv/backend
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt requests==2.34.2 \
    && useradd --uid 10001 --create-home app && mkdir /srv/frontend
COPY backend/ /srv/backend/
COPY shared/ /srv/shared/
USER 10001
EXPOSE 8001
HEALTHCHECK --interval=15s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health/live', timeout=3)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--no-access-log"]
