#!/usr/bin/env bash
# Recreate the PickleTV database, role, schema, and tables.
# Usage: ./scripts/recreate_database.sh <app_password>
# Optional environment variables:
#   PGHOST (default: localhost)
#   PGPORT (default: 5432)
#   PG_SUPERUSER (default: postgres)
#   TV_DB_NAME (default: tv_dbase)
#   TV_APP_USER (default: tv_api_app)
#   TV_APP_SCHEMA (default: tv_app)

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <app_password>" >&2
    exit 1
fi

APP_PASSWORD="$1"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PG_SUPERUSER="${PG_SUPERUSER:-postgres}"
TV_DB_NAME="${TV_DB_NAME:-tv_dbase}"
TV_APP_USER="${TV_APP_USER:-tv_api_app}"
TV_APP_SCHEMA="${TV_APP_SCHEMA:-tv_app}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCHEMA_FILE="${REPO_ROOT}/db/schema.sql"
SEED_FILE="${REPO_ROOT}/db/seed.sql"

if [[ ! -f "${SCHEMA_FILE}" ]]; then
    echo "Schema file not found at ${SCHEMA_FILE}" >&2
    exit 1
fi

validate_identifier() {
    local identifier="$1"
    if [[ ! "${identifier}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
        echo "Invalid identifier: ${identifier}" >&2
        exit 1
    fi
}

escape_literal() {
    printf "%s" "$1" | sed "s/'/''/g"
}

validate_identifier "${TV_DB_NAME}"
validate_identifier "${TV_APP_USER}"
validate_identifier "${TV_APP_SCHEMA}"

APP_PASSWORD_SQL="$(escape_literal "${APP_PASSWORD}")"

psql_admin=(psql -v ON_ERROR_STOP=1 -h "${PGHOST}" -p "${PGPORT}" -U "${PG_SUPERUSER}" postgres)

# Drop existing connections, database, and role if they exist.
"${psql_admin[@]}" <<SQL
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '${TV_DB_NAME}'
    AND pid <> pg_backend_pid();

DROP DATABASE IF EXISTS ${TV_DB_NAME};
DO \$\$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${TV_APP_USER}') THEN
        EXECUTE format('DROP OWNED BY %I CASCADE', '${TV_APP_USER}');
        EXECUTE format('DROP ROLE %I', '${TV_APP_USER}');
    END IF;
END;
\$\$;
SQL

# Recreate the role and database owned by that role.
"${psql_admin[@]}" <<SQL
CREATE ROLE ${TV_APP_USER}
    WITH LOGIN PASSWORD '${APP_PASSWORD_SQL}'
    NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE DATABASE ${TV_DB_NAME} OWNER ${TV_APP_USER};
REVOKE ALL ON DATABASE ${TV_DB_NAME} FROM PUBLIC;
GRANT CONNECT ON DATABASE ${TV_DB_NAME} TO ${TV_APP_USER};
SQL

psql_db=(psql -v ON_ERROR_STOP=1 -h "${PGHOST}" -p "${PGPORT}" -U "${PG_SUPERUSER}" "${TV_DB_NAME}")

# Configure schema, search path, and default privileges.
"${psql_db[@]}" <<SQL
ALTER ROLE ${TV_APP_USER} IN DATABASE ${TV_DB_NAME}
    SET search_path = ${TV_APP_SCHEMA}, public;
CREATE SCHEMA IF NOT EXISTS ${TV_APP_SCHEMA} AUTHORIZATION ${TV_APP_USER};
GRANT USAGE ON SCHEMA ${TV_APP_SCHEMA} TO ${TV_APP_USER};
ALTER DEFAULT PRIVILEGES FOR ROLE ${TV_APP_USER} IN SCHEMA ${TV_APP_SCHEMA}
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ${TV_APP_USER};
ALTER DEFAULT PRIVILEGES FOR ROLE ${TV_APP_USER} IN SCHEMA ${TV_APP_SCHEMA}
    GRANT USAGE, SELECT ON SEQUENCES TO ${TV_APP_USER};
SQL

# Create tables and indexes.
"${psql_db[@]}" -v schema_name="${TV_APP_SCHEMA}" -f "${SCHEMA_FILE}"

# Grant permissions on magic_links table and any sequences.
"${psql_db[@]}" <<SQL
GRANT ALL PRIVILEGES ON TABLE ${TV_APP_SCHEMA}.magic_links TO ${TV_APP_USER};
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA ${TV_APP_SCHEMA} TO ${TV_APP_USER};
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA ${TV_APP_SCHEMA} TO ${TV_APP_USER};
SQL

echo "Database ${TV_DB_NAME} recreated."
echo "Run db/seed.sql if you need sample data:"
echo "  psql \"postgresql://${TV_APP_USER}:<PASSWORD>@${PGHOST}:${PGPORT}/${TV_DB_NAME}\" -f ${SEED_FILE}"
