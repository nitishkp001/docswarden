"""DB connection, schema creation, and XDG path resolution.

All runtime paths go through this module. Tests override via
$DOCWARDEN_DATA_DIR so they never touch the real user data dir.
"""

import os
import sqlite3
from pathlib import Path


def data_dir() -> Path:
    override = os.environ.get("DOCWARDEN_DATA_DIR")
    if override:
        return Path(override)
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "docwarden"


def db_path() -> Path:
    return data_dir() / "index.db"


def get_connection() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _assert_fts5(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _fts5_probe USING fts5(x)")
        conn.execute("DROP TABLE IF EXISTS _fts5_probe")
    except sqlite3.OperationalError as exc:
        raise RuntimeError(
            "This Python installation's SQLite was compiled without FTS5 support. "
            "docwarden requires FTS5. Try upgrading Python or using uv."
        ) from exc


def init_schema(conn: sqlite3.Connection) -> None:
    _assert_fts5(conn)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS pages (
            id           INTEGER PRIMARY KEY,
            framework    TEXT    NOT NULL,
            url          TEXT    NOT NULL,
            title        TEXT,
            indexed_at   TEXT    NOT NULL,
            content_hash TEXT    NOT NULL,
            UNIQUE(framework, url)
        );

        CREATE TABLE IF NOT EXISTS chunks (
            id            INTEGER PRIMARY KEY,
            page_id       INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
            framework     TEXT    NOT NULL,
            breadcrumb    TEXT    NOT NULL,
            section_title TEXT,
            anchor        TEXT,
            content       TEXT    NOT NULL,
            ord           INTEGER NOT NULL
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            breadcrumb, section_title, content,
            content='chunks', content_rowid='id',
            tokenize='porter unicode61'
        );

        CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
            INSERT INTO chunks_fts(rowid, breadcrumb, section_title, content)
            VALUES (new.id, new.breadcrumb, new.section_title, new.content);
        END;

        CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, breadcrumb, section_title, content)
            VALUES ('delete', old.id, old.breadcrumb, old.section_title, old.content);
        END;

        CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, breadcrumb, section_title, content)
            VALUES ('delete', old.id, old.breadcrumb, old.section_title, old.content);
            INSERT INTO chunks_fts(rowid, breadcrumb, section_title, content)
            VALUES (new.id, new.breadcrumb, new.section_title, new.content);
        END;
    """)
    conn.commit()
