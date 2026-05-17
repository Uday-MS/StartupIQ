# =============================================================================
# DATABASE MODULE — PostgreSQL (primary) + SQLite (fallback)
# Provides get_conn() / put_conn() / init_db() that work with both backends.
# All other modules (auth.py, app.py) use these functions unchanged.
# =============================================================================
import os
import re
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()  # Safe for local + Render

print("DATABASE_URL present:", bool(os.getenv("DATABASE_URL")))

DATABASE_URL = os.getenv("DATABASE_URL")

# ---------------------------------------------------------------------------
# Detect database mode
# ---------------------------------------------------------------------------
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    from psycopg2 import pool

SQLITE_DB_PATH = os.path.join(os.path.dirname(__file__), "startupiq.db")


# =============================================================================
# SQLite Wrappers — mimic psycopg2 cursor/connection API
# So existing code (auth.py, app.py) works with zero changes.
# =============================================================================

class _SQLiteCursorWrapper:
    """Wraps sqlite3.Cursor to behave like a psycopg2 cursor.

    Key adaptations:
    - Converts %s placeholders to ?
    - Handles RETURNING id clause via cursor.lastrowid
    - Exposes rowcount property
    """

    def __init__(self, cursor):
        self._cursor = cursor
        self._returning = False
        self._lastrowid = None

    def execute(self, sql, params=None):
        # Convert PostgreSQL %s placeholders to SQLite ?
        sql = sql.replace("%s", "?")

        # Handle RETURNING <col> clause (PostgreSQL-specific)
        self._returning = False
        if " RETURNING " in sql.upper():
            sql = re.sub(r"\s+RETURNING\s+\w+", "", sql, flags=re.IGNORECASE)
            self._returning = True

        if params:
            self._cursor.execute(sql, params)
        else:
            self._cursor.execute(sql)

        if self._returning:
            self._lastrowid = self._cursor.lastrowid

    def fetchone(self):
        # If the last execute had RETURNING, return (lastrowid,)
        if self._returning and self._lastrowid is not None:
            row_id = self._lastrowid
            self._returning = False
            self._lastrowid = None
            return (row_id,)
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def close(self):
        self._cursor.close()


class _SQLiteConnectionWrapper:
    """Wraps sqlite3.Connection to behave like a psycopg2 connection.

    - cursor() returns the wrapper cursor
    - commit() / rollback() delegate to the real connection
    - WAL mode + foreign keys enabled for performance and integrity
    """

    def __init__(self, db_path):
        self._conn = sqlite3.connect(
            db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            check_same_thread=False,
        )
        # Performance: WAL mode allows concurrent reads
        self._conn.execute("PRAGMA journal_mode=WAL")
        # Integrity: enforce foreign key constraints
        self._conn.execute("PRAGMA foreign_keys=ON")

    def cursor(self):
        return _SQLiteCursorWrapper(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


# =============================================================================
# Connection Management — Pool (PostgreSQL) / Factory (SQLite)
# =============================================================================
_pool = None


def get_pool():
    """Get or create the PostgreSQL connection pool (lazy singleton)."""
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=DATABASE_URL,
            sslmode="require"
        )
        print("✅ PostgreSQL connection pool created")
    return _pool


def get_conn():
    """Get a database connection.

    PostgreSQL: borrow from the connection pool.
    SQLite: create a new connection (lightweight, closed in put_conn).
    """
    if USE_POSTGRES:
        return get_pool().getconn()
    else:
        return _SQLiteConnectionWrapper(SQLITE_DB_PATH)


def put_conn(conn):
    """Return / close a database connection.

    PostgreSQL: return to the connection pool.
    SQLite: close the connection.
    """
    if USE_POSTGRES:
        get_pool().putconn(conn)
    else:
        try:
            conn.close()
        except Exception:
            pass


# =============================================================================
# Table Creation — PostgreSQL or SQLite (safe, idempotent)
# =============================================================================

def _init_postgres(conn):
    """Create tables and run migrations for PostgreSQL."""
    cur = conn.cursor()

    # ---- Users table ----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            SERIAL PRIMARY KEY,
            username      VARCHAR(80) NOT NULL,
            email         VARCHAR(120) NOT NULL UNIQUE,
            password_hash TEXT,
            google_id     VARCHAR(255) UNIQUE,
            reset_token   VARCHAR(255),
            token_expiry  TIMESTAMP,
            created_at    TIMESTAMP DEFAULT NOW()
        );
    """)

    # ---- Migrate: add missing columns safely ----
    for col, col_type in [
        ("google_id", "VARCHAR(255) UNIQUE"),
        ("reset_token", "VARCHAR(255)"),
        ("token_expiry", "TIMESTAMP"),
        ("is_verified", "BOOLEAN DEFAULT FALSE"),
        ("verification_token", "VARCHAR(255)"),
        ("verification_expiry", "TIMESTAMP"),
        ("otp_hash", "VARCHAR(255)"),
        ("otp_expiry", "TIMESTAMP"),
        ("otp_attempts", "INTEGER DEFAULT 0"),
        ("otp_last_sent", "TIMESTAMP"),
    ]:
        cur.execute(f"""
            DO $$
            BEGIN
                ALTER TABLE users ADD COLUMN {col} {col_type};
            EXCEPTION WHEN duplicate_column THEN
                NULL;
            END $$;
        """)

    # Make password_hash nullable (Google users don't have passwords)
    cur.execute("""
        ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;
    """)

    # ---- Saved Startups table ----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS saved_startups (
            id           SERIAL PRIMARY KEY,
            user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            startup_name VARCHAR(255) NOT NULL,
            industry     VARCHAR(255),
            country      VARCHAR(255),
            funding      FLOAT DEFAULT 0,
            created_at   TIMESTAMP DEFAULT NOW()
        );
    """)

    # ---- Migrate saved_startups: add missing columns safely ----
    for col, col_type in [
        ("industry", "VARCHAR(255)"),
        ("country", "VARCHAR(255)"),
        ("funding", "FLOAT DEFAULT 0"),
    ]:
        cur.execute(f"""
            DO $$
            BEGIN
                ALTER TABLE saved_startups ADD COLUMN {col} {col_type};
            EXCEPTION WHEN duplicate_column THEN
                NULL;
            END $$;
        """)

    conn.commit()
    cur.close()
    print("✅ Database tables initialized (PostgreSQL)")


def _init_sqlite(conn):
    """Create tables for SQLite.

    No migration needed — CREATE TABLE IF NOT EXISTS handles everything.
    Schema matches PostgreSQL but uses SQLite-compatible types.
    """
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            username            TEXT NOT NULL,
            email               TEXT NOT NULL UNIQUE,
            password_hash       TEXT,
            google_id           TEXT UNIQUE,
            reset_token         TEXT,
            token_expiry        TIMESTAMP,
            is_verified         BOOLEAN DEFAULT 0,
            verification_token  TEXT,
            verification_expiry TIMESTAMP,
            otp_hash            TEXT,
            otp_expiry          TIMESTAMP,
            otp_attempts        INTEGER DEFAULT 0,
            otp_last_sent       TIMESTAMP,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS saved_startups (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            startup_name TEXT NOT NULL,
            industry     TEXT,
            country      TEXT,
            funding      REAL DEFAULT 0,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    cur.close()
    print("✅ Database tables initialized (SQLite)")


def init_db():
    """Create all required tables if they don't exist."""
    conn = get_conn()
    try:
        if USE_POSTGRES:
            _init_postgres(conn)
        else:
            _init_sqlite(conn)
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"❌ Database init failed: {e}")
    finally:
        put_conn(conn)


# ---------------------------------------------------------------------------
# Print database mode on import
# ---------------------------------------------------------------------------
if USE_POSTGRES:
    print(f"📦 Database mode: PostgreSQL")
else:
    print(f"📦 Database mode: SQLite ({SQLITE_DB_PATH})")


# ---------------------------------------------------------------------------
# Run init on module import IF called directly (also safe to call from app.py)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    init_db()
    print("Database setup complete.")
