FROM python:3.12-slim
WORKDIR /app
RUN apt-get update \
	&& apt-get install --no-install-recommends --yes tesseract-ocr \
	&& rm -rf /var/lib/apt/lists/*
COPY apps/api/pyproject.toml .
RUN pip install --no-cache-dir ".[dev]"
COPY apps/api/app ./app
COPY apps/api/alembic ./alembic
COPY apps/api/alembic.ini ./alembic.ini
COPY apps/api/tests ./tests
COPY prompts /prompts
COPY rules /rules
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
