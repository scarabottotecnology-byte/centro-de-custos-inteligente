# Contexto de build: a pasta prospeccao/ (o esquema SQL vai junto com o código).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=America/Sao_Paulo \
    PROSPECTOR_SCHEMA=/app/db/init/001_schema.sql
WORKDIR /app

COPY prospector/pyproject.toml prospector/
COPY prospector/prospector prospector/prospector
RUN pip install --no-cache-dir ./prospector

COPY db db

VOLUME ["/data"]
EXPOSE 8000
ENTRYPOINT ["prospector"]
CMD ["servidor"]
