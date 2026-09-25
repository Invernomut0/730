FROM python:3.12-slim
WORKDIR /app
COPY apps/api/pyproject.toml .
RUN pip install --no-cache-dir ".[dev]"
COPY apps/api/app ./app
COPY apps/api/alembic ./alembic
COPY apps/api/alembic.ini ./alembic.ini
COPY apps/api/tests ./tests
COPY prompts /prompts
COPY rules /rules
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
