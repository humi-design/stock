"""Database access layer.

Switches transparently between MySQL (when DB_HOST is configured) and
SQLite (fallback). SQLite tables are created automatically on first use.
MySQL users can create tables from schema.sql.
"""
import sqlite3

from config import config

# Thread-local connections so Flask dev server threads stay isolated.
import threading

_thread_local = threading.local()


class Database:
    def __init__(self):
        self.engine = "mysql" if config.USE_MYSQL else "sqlite"

    # ------------------------------------------------------------------ #
    # Connection handling
    # ------------------------------------------------------------------ #
    @property
    def connection(self):
        if self.engine == "mysql":
            return self._mysql_connection()
        return self._sqlite_connection()

    def _mysql_connection(self):
        import mysql.connector

        if not hasattr(_thread_local, "mysql_conn"):
            _thread_local.mysql_conn = mysql.connector.connect(
                host=config.DB_HOST,
                port=config.DB_PORT,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                database=config.DB_NAME,
                autocommit=False,
            )
            _thread_local.mysql_connected = False
        conn = _thread_local.mysql_conn
        # Reconnect if the connection was dropped.
        if not _thread_local.mysql_connected:
            try:
                conn.ping(reconnect=True, attempts=2, delay=1)
            except Exception:
                raise
            _thread_local.mysql_connected = True
        return conn

    def _sqlite_connection(self):
        if not hasattr(_thread_local, "sqlite_conn"):
            conn = sqlite3.connect(config.SQLITE_PATH, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            _thread_local.sqlite_conn = conn
            _thread_local.sqlite_created = False
        conn = _thread_local.sqlite_conn
        if not _thread_local.sqlite_created:
            self._create_tables(conn)
            _thread_local.sqlite_created = True
        return conn

    # ------------------------------------------------------------------ #
    # Schema
    # ------------------------------------------------------------------ #
    def _create_tables(self, conn):
        """Create minimal tables (SQLite). MySQL uses schema.sql."""
        statements = [
            """
            CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_ref TEXT UNIQUE,
                case_type TEXT,
                reference TEXT,
                amount REAL,
                currency TEXT,
                severity TEXT,
                status TEXT,
                root_cause TEXT,
                recommendation TEXT,
                confidence REAL,
                evidence TEXT,
                created_at TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS case_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER,
                event_type TEXT,
                detail TEXT,
                created_at TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                company TEXT,
                email TEXT,
                phone TEXT,
                role TEXT,
                company_type TEXT,
                process TEXT,
                created_at TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS ai_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT,
                model TEXT,
                case_id TEXT,
                prompt_type TEXT,
                success INTEGER,
                latency_ms INTEGER,
                created_at TEXT
            )
            """,
        ]
        for stmt in statements:
            conn.execute(stmt)
        conn.commit()

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #
    def execute(self, sql, params=()):
        conn = self.connection
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            conn.commit()
            if self.engine == "mysql" and cur.lastrowid is None:
                return cur
            return cur
        except Exception:
            conn.rollback()
            raise

    def query(self, sql, params=()):
        conn = self.connection
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return rows

    def query_one(self, sql, params=()):
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def row_to_dict(self, row):
        if row is None:
            return None
        return {k: row[k] for k in row.keys()}


db = Database()