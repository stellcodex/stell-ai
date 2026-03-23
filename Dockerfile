FROM python:3.11-slim

WORKDIR /srv

RUN apt-get update \
  && apt-get install -y --no-install-recommends curl netcat-openbsd \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /srv/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /srv/requirements.txt

COPY runtime_app /srv/runtime_app

ENV PYTHONPATH=/srv

CMD ["sh", "-lc", "\
  DB_HOST=${DB_HOST:-postgres}; DB_PORT=${DB_PORT:-5432}; BACKEND_HOST=${BACKEND_HOST:-backend}; BACKEND_PORT=${BACKEND_PORT:-8000}; \
  echo \"Waiting for ${DB_HOST}:${DB_PORT}...\" && until nc -z ${DB_HOST} ${DB_PORT}; do sleep 1; done; \
  echo \"Waiting for ${BACKEND_HOST}:${BACKEND_PORT}...\" && until nc -z ${BACKEND_HOST} ${BACKEND_PORT}; do sleep 1; done; \
  uvicorn runtime_app.main:app --host 0.0.0.0 --port 7020 \
"]
