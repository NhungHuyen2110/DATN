FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 AI_PIPELINE=modular HF_HOME=/srv/model-cache
WORKDIR /srv/AI
COPY AI/requirements-runtime.txt AI/requirements-semantic.txt ./
RUN pip install --no-cache-dir -r requirements-semantic.txt && useradd --uid 10001 --create-home lumiere && mkdir -p /srv/model-cache && chown lumiere:lumiere /srv/model-cache
COPY AI /srv/AI
COPY output/products_ai.csv output/orders.csv output/order_details.csv /srv/output/
USER lumiere
EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3)"
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
