FROM postgres:16-alpine

ENV POSTGRES_DB=sigint_db
ENV POSTGRES_USER=sigint
ENV POSTGRES_PASSWORD=sigint_secure_2024

COPY init/001_schema.sql /docker-entrypoint-initdb.d/001_schema.sql
COPY seed/seed_data.sql /docker-entrypoint-initdb.d/002_seed_data.sql

HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
  CMD pg_isready -U sigint -d sigint_db || exit 1

EXPOSE 5432
