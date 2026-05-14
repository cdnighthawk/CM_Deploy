-- One-time database bootstrap for USIS CM.
-- Run as the `postgres` superuser; the application user/role and database
-- are created here. Schema objects (tables, enums, etc.) are NOT created
-- here -- that is Alembic's job.
--
-- Run via the PowerShell helper:
--   scripts\bootstrap_db.ps1
-- ...or manually:
--   psql -U postgres -h localhost -v usis_db=usis_cm \
--        -v usis_role=usis_app -v usis_pw='YOUR_PASSWORD' \
--        -f scripts\bootstrap_db.sql

\set ON_ERROR_STOP on

-- Create the role if it doesn't exist; update the password if it does.
DO
$$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'usis_role') THEN
        EXECUTE format(
            'CREATE ROLE %I LOGIN PASSWORD %L',
            :'usis_role',
            :'usis_pw'
        );
    ELSE
        EXECUTE format(
            'ALTER ROLE %I WITH LOGIN PASSWORD %L',
            :'usis_role',
            :'usis_pw'
        );
    END IF;
END
$$;

-- Create the database if it doesn't exist (cannot run inside DO block).
SELECT 'CREATE DATABASE ' || quote_ident(:'usis_db') ||
       ' OWNER ' || quote_ident(:'usis_role') ||
       ' ENCODING ''UTF8'' TEMPLATE template0'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'usis_db')
\gexec

GRANT ALL PRIVILEGES ON DATABASE :"usis_db" TO :"usis_role";

\connect :"usis_db"

-- Make sure the app role can use the public schema and create future
-- objects there (Alembic migrations run as this role).
GRANT USAGE, CREATE ON SCHEMA public TO :"usis_role";
ALTER SCHEMA public OWNER TO :"usis_role";

-- pgcrypto provides gen_random_uuid() on older Postgres; on PG13+ it is
-- also exposed by default, but we install the extension for portability.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

\echo ''
\echo 'Bootstrap complete.'
\echo '  Database : ':"usis_db"
\echo '  Role     : ':"usis_role"
\echo ''
\echo 'Next step: from the backend folder, run:'
\echo '    flask db upgrade'
