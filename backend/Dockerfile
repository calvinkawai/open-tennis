FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 ANONYMIZED_TELEMETRY=False
COPY pyproject.toml uv.lock README.md ./
RUN pip install --no-cache-dir uv==0.11.16
COPY app ./app
RUN uv export --frozen --no-dev --no-emit-project --format requirements-txt --output-file /tmp/requirements.txt \
    && pip install --no-cache-dir -r /tmp/requirements.txt
COPY main.py alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts
COPY data/tutorial ./data/tutorial
RUN useradd --uid 10001 --create-home tennis && mkdir -p /data && chown tennis:tennis /data
USER tennis
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]
