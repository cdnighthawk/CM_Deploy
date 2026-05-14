"""Create/update the app DB role and database using the superuser from .env.

Same outcome as ``bootstrap_db.ps1`` + ``bootstrap_db.sql``, without requiring
``psql`` on PATH. Run from repo root or anywhere:

    python scripts/bootstrap_db.py

Loads ``backend/.env`` when run from ``backend/`` (cwd), or set env vars yourself.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from psycopg import sql
from psycopg.conninfo import make_conninfo


def _load_dotenv() -> Path:
    backend = Path(__file__).resolve().parents[1]
    env_path = backend / ".env"
    if env_path.is_file():
        load_dotenv(env_path)
    else:
        load_dotenv()
    return backend


def main() -> int:
    _load_dotenv()

    super_pw = (os.environ.get("POSTGRES_SUPERUSER_PASSWORD") or "").strip()
    app_pw = (os.environ.get("USIS_APP_DB_PASSWORD") or "").strip()
    if not super_pw or not app_pw:
        print("Set POSTGRES_SUPERUSER_PASSWORD and USIS_APP_DB_PASSWORD in .env", file=sys.stderr)
        return 1

    db_name = os.environ.get("USIS_DB_NAME", "usis_cm")
    app_role = os.environ.get("USIS_APP_ROLE", "usis_app")
    # Prefer 127.0.0.1 over "localhost": on Windows, localhost often resolves to
    # ::1 first; pg_hba can differ for IPv4 vs IPv6 so pgAdmin (IPv4) may work while
    # libpq hits ::1 and fails password auth.
    host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
    if host.strip().lower() == "localhost":
        host = "127.0.0.1"
    port = int(os.environ.get("POSTGRES_PORT", "5432"))
    super_user = os.environ.get("POSTGRES_SUPERUSER_USER", "postgres")

    super_conninfo = make_conninfo(
        host=host,
        port=port,
        dbname="postgres",
        user=super_user,
        password=super_pw,
        sslmode=os.environ.get("POSTGRES_SSLMODE", "prefer"),
    )

    import psycopg

    with psycopg.connect(super_conninfo, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (app_role,))
            if cur.fetchone():
                cur.execute(
                    sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
                        sql.Identifier(app_role),
                        sql.Literal(app_pw),
                    )
                )
            else:
                cur.execute(
                    sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                        sql.Identifier(app_role),
                        sql.Literal(app_pw),
                    )
                )

            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
            if not cur.fetchone():
                cur.execute(
                    sql.SQL(
                        "CREATE DATABASE {} OWNER {} ENCODING 'UTF8' TEMPLATE template0"
                    ).format(sql.Identifier(db_name), sql.Identifier(app_role))
                )

            cur.execute(
                sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
                    sql.Identifier(db_name),
                    sql.Identifier(app_role),
                )
            )

    db_conninfo = make_conninfo(
        host=host,
        port=port,
        dbname=db_name,
        user=super_user,
        password=super_pw,
        sslmode=os.environ.get("POSTGRES_SSLMODE", "prefer"),
    )
    with psycopg.connect(db_conninfo, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL("GRANT USAGE, CREATE ON SCHEMA public TO {}").format(
                    sql.Identifier(app_role)
                )
            )
            cur.execute(
                sql.SQL("ALTER SCHEMA public OWNER TO {}").format(sql.Identifier(app_role))
            )
            cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    print(f"Bootstrap OK: database={db_name!r} role={app_role!r}")
    print("Next: flask db upgrade")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
