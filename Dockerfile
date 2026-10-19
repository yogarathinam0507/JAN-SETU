FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt backend/requirements-postgres.txt backend/
RUN pip install --no-cache-dir -r backend/requirements-postgres.txt
COPY backend backend
COPY frontend frontend
COPY scripts scripts
RUN useradd -m jansetu && mkdir -p /app/backend/data && chown -R jansetu /app/backend/data
USER jansetu
WORKDIR /app/backend
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health')" || exit 1
CMD ["sh", "-c", "alembic upgrade head && if [ \"$SEED_DEMO\" = \"true\" ]; then python -m app.seed; fi && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
