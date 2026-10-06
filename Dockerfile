FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-production.txt requirements-test.txt ./

RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements-production.txt \
    && python -m pip install -r requirements-test.txt

COPY course_recommender ./course_recommender
COPY scripts ./scripts
COPY tests ./tests
COPY .env.example README.md ./

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/data /app/course_recommender_artifacts_final \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=5).read()"

CMD ["python", "-m", "uvicorn", "course_recommender.api:app", "--host", "0.0.0.0", "--port", "8001"]
