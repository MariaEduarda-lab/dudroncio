# Imagem oficial e publica do PostgreSQL.
FROM postgres:16

# O primeiro script cria/restringe o papel usado pela API. O schema roda
# depois, autenticado como database_owner (POSTGRES_USER), e termina com os
# grants minimos para application_user.
COPY init-runtime-role.sh /docker-entrypoint-initdb.d/01-runtime-role.sh
COPY database.sql /docker-entrypoint-initdb.d/02-database.sql
