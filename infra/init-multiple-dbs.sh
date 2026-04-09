#!/bin/bash
# Creates multiple PostgreSQL databases in one init run
# Used by docker-compose to create: quantagents, airflow, mlflow

set -e
set -u

function create_db() {
    local database=$1
    echo "Creating database: $database"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
        SELECT 'CREATE DATABASE $database'
        WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$database')\gexec
EOSQL
}

create_db "airflow"
create_db "mlflow"
# quantagents already exists (it's POSTGRES_DB)
