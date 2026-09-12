"""
Слой доступа к БД. SQLite для старта (без внешних зависимостей, работает на Termux).
Когда/если понадобится переезд на Postgres под нагрузку SaaS — меняется только DB_PATH/DSN здесь.
"""
import sqlite3
import json
import os
from contextlib import contextmanager

DB_PATH = os.environ.get("DEMAND_RADAR_DB", os.path.join(os.path.dirname(__file__), "demand_radar.db"))
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def upsert_source(code, name, kind, config: dict, enabled=True):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO sources (code, name, kind, enabled, config_json)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(code) DO UPDATE SET
                 name=excluded.name, kind=excluded.kind,
                 enabled=excluded.enabled, config_json=excluded.config_json""",
            (code, name, kind, int(enabled), json.dumps(config, ensure_ascii=False)),
        )


def get_enabled_sources():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM sources WHERE enabled=1").fetchall()
        return [dict(r) for r in rows]


def insert_raw_message(source_id, external_id, author, text, url, posted_at):
    """Возвращает id вставленной строки, либо None если дубликат."""
    with get_conn() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO raw_messages (source_id, external_id, author, text, url, posted_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (source_id, external_id, author, text, url, posted_at),
            )
            return cur.lastrowid
        except sqlite3.IntegrityError:
            return None  # уже собирали это сообщение


def get_unfiltered_messages(limit=500):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM raw_messages WHERE prefiltered=0 LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def mark_prefiltered(message_ids, passed_ids):
    with get_conn() as conn:
        conn.executemany(
            "UPDATE raw_messages SET prefiltered=1 WHERE id=?",
            [(i,) for i in message_ids],
        )


def get_unclassified_messages(limit=100):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM raw_messages WHERE prefiltered=1 AND classified=0 LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def save_demand_signal(raw_message_id, is_demand, category, normalized_query, confidence, reasoning):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO demand_signals
               (raw_message_id, is_demand, category, normalized_query, confidence, reasoning)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (raw_message_id, int(is_demand), category, normalized_query, confidence, reasoning),
        )
        conn.execute("UPDATE raw_messages SET classified=1 WHERE id=?", (raw_message_id,))


def get_top_categories(days=30, limit=20):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT category, COUNT(*) as cnt
               FROM demand_signals
               WHERE is_demand=1 AND created_at >= datetime('now', ?)
               GROUP BY category
               ORDER BY cnt DESC
               LIMIT ?""",
            (f"-{days} days", limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_recent_signals(category=None, limit=50):
    with get_conn() as conn:
        if category:
            rows = conn.execute(
                """SELECT ds.*, rm.text, rm.url, rm.posted_at, s.name as source_name
                   FROM demand_signals ds
                   JOIN raw_messages rm ON rm.id = ds.raw_message_id
                   JOIN sources s ON s.id = rm.source_id
                   WHERE ds.is_demand=1 AND ds.category=?
                   ORDER BY ds.created_at DESC LIMIT ?""",
                (category, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT ds.*, rm.text, rm.url, rm.posted_at, s.name as source_name
                   FROM demand_signals ds
                   JOIN raw_messages rm ON rm.id = ds.raw_message_id
                   JOIN sources s ON s.id = rm.source_id
                   WHERE ds.is_demand=1
                   ORDER BY ds.created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
