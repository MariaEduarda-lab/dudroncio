#!/usr/bin/env bash
set -Eeuo pipefail

: "${APPLICATION_DB_PASSWORD:?APPLICATION_DB_PASSWORD precisa estar definido}"

# A imagem oficial executa este arquivo somente na criacao do cluster. O nome
# do papel e fixo; apenas a senha vem do ambiente e entra no SQL como literal
# escapado pelo proprio psql/PostgreSQL.
psql -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set=database_name="$POSTGRES_DB" \
  --set=application_password="$APPLICATION_DB_PASSWORD" <<-'EOSQL'
SELECT format(
    'CREATE ROLE application_user LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD %L',
    :'application_password'
) WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'application_user') \gexec

ALTER ROLE application_user NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
REVOKE ALL ON DATABASE :"database_name" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"database_name" TO application_user;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
EOSQL
