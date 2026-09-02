ARG PYTHON_IMAGE=python:3.14.7-slim-trixie
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# OpenCV's headless wheel needs the GNU OpenMP runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.lock.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.lock.txt

RUN addgroup --system app \
    && adduser --system --ingroup app --home /app app

COPY . .
RUN python manage.py collectstatic --noinput \
    && chmod +x scripts/*.sh \
    && chown -R app:app /app

USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, socket; sock = socket.create_connection(('127.0.0.1', int(os.environ.get('PORT', '8000'))), timeout=3); sock.close()"

CMD ["sh", "scripts/web.sh"]
