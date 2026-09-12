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


def _migrate(conn):
    """Добавляет новые колонки в уже существующие (созданные до этого изменения)
    таблицы. CREATE TABLE IF NOT EXISTS в schema.sql не трогает уже существующие
    таблицы, поэтому колонки, добавленные позже первого релиза, нужно домигрировать
    отдельно — по одной ALTER TABLE на колонку, игнорируя ошибку если она уже есть."""
    migrations = [
        "ALTER TABLE sources ADD COLUMN signal_type TEXT DEFAULT 'demand'",
        "ALTER TABLE raw_messages ADD COLUMN signal_type TEXT DEFAULT 'demand'",
    ]
    for stmt in migrations:
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError:
            pass  # колонка уже существует — нормально


def init_db():
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    _migrate(conn)
    conn.commit()
    conn.close()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # SQLite's built-in LOWER() only handles ASCII — Cyrillic "А" не приводится к "а".
    # Регистрируем свою функцию на Python (str.lower() умеет в юникод как надо),
    # используется в get_matches/get_match_categories для сравнения категорий.
    conn.create_function("PYLOWER", 1, lambda s: s.lower() if s else s)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def upsert_source(code, name, kind, config: dict, enabled=True, signal_type="demand"):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO sources (code, name, kind, signal_type, enabled, config_json)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(code) DO UPDATE SET
                 name=excluded.name, kind=excluded.kind, signal_type=excluded.signal_type,
                 enabled=excluded.enabled, config_json=excluded.config_json""",
            (code, name, kind, signal_type, int(enabled), json.dumps(config, ensure_ascii=False)),
        )


def get_enabled_sources():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM sources WHERE enabled=1").fetchall()
        return [dict(r) for r in rows]


def insert_raw_message(source_id, external_id, author, text, url, posted_at, signal_type="demand"):
    """Возвращает id вставленной строки, либо None если дубликат."""
    with get_conn() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO raw_messages (source_id, external_id, author, text, url, posted_at, signal_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (source_id, external_id, author, text, url, posted_at, signal_type),
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


def get_unclassified_messages(limit=100, signal_type="demand"):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM raw_messages WHERE prefiltered=1 AND classified=0 AND signal_type=? LIMIT ?",
            (signal_type, limit),
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


def save_supply_signal(raw_message_id, is_giveaway, category, normalized_item, value_note, confidence, reasoning):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO supply_signals
               (raw_message_id, is_giveaway, category, normalized_item, value_note, confidence, reasoning)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (raw_message_id, int(is_giveaway), category, normalized_item, value_note, confidence, reasoning),
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


def get_recent_supply_signals(category=None, limit=50):
    with get_conn() as conn:
        if category:
            rows = conn.execute(
                """SELECT ss.*, rm.text, rm.url, rm.posted_at, s.name as source_name
                   FROM supply_signals ss
                   JOIN raw_messages rm ON rm.id = ss.raw_message_id
                   JOIN sources s ON s.id = rm.source_id
                   WHERE ss.is_giveaway=1 AND ss.category=?
                   ORDER BY ss.created_at DESC LIMIT ?""",
                (category, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT ss.*, rm.text, rm.url, rm.posted_at, s.name as source_name
                   FROM supply_signals ss
                   JOIN raw_messages rm ON rm.id = ss.raw_message_id
                   JOIN sources s ON s.id = rm.source_id
                   WHERE ss.is_giveaway=1
                   ORDER BY ss.created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


def get_matches(limit=100):
    """Сводит спрос и предложение по одинаковой категории — это и есть готовые
    арбитражные возможности: кто-то отдаёт X даром/дёшево, кто-то платит за X.
    Категория сравнивается без учёта регистра (обе стороны классифицируются
    одним и тем же списком категорий, но модель может слегка разойтись в регистре)."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT
                 ss.category AS category,
                 ss.normalized_item AS supply_item, ss.value_note AS supply_value,
                 ss.confidence AS supply_confidence,
                 rm_s.url AS supply_url, rm_s.text AS supply_text, s_s.name AS supply_source,
                 ds.normalized_query AS demand_query, ds.confidence AS demand_confidence,
                 rm_d.url AS demand_url, rm_d.text AS demand_text, s_d.name AS demand_source,
                 ss.created_at AS supply_created_at, ds.created_at AS demand_created_at
               FROM supply_signals ss
               JOIN raw_messages rm_s ON rm_s.id = ss.raw_message_id
               JOIN sources s_s ON s_s.id = rm_s.source_id
               JOIN demand_signals ds ON PYLOWER(TRIM(ds.category)) = PYLOWER(TRIM(ss.category))
               JOIN raw_messages rm_d ON rm_d.id = ds.raw_message_id
               JOIN sources s_d ON s_d.id = rm_d.source_id
               WHERE ss.is_giveaway=1 AND ds.is_demand=1
               ORDER BY ss.created_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_match_categories():
    """Категории, где есть совпадение и по спросу, и по предложению — только они
    дают реальные арбитражные пары, остальное показывать в /matches бессмысленно."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT DISTINCT PYLOWER(TRIM(ss.category)) as category
               FROM supply_signals ss
               JOIN demand_signals ds ON PYLOWER(TRIM(ds.category)) = PYLOWER(TRIM(ss.category))
               WHERE ss.is_giveaway=1 AND ds.is_demand=1"""
        ).fetchall()
        return [r["category"] for r in rows]
