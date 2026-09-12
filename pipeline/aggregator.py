"""
Агрегация demand_signals в тренды по категориям за период (запускается по расписанию,
например раз в сутки/неделю через cron/Termux:Boot).
"""
import json
from datetime import datetime, timedelta
from db.db import get_conn


def build_weekly_trends():
    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=7)

    with get_conn() as conn:
        rows = conn.execute(
            """SELECT category, normalized_query
               FROM demand_signals
               WHERE is_demand=1 AND created_at >= ?""",
            (period_start.isoformat(),),
        ).fetchall()

        by_category = {}
        for r in rows:
            cat = r["category"] or "без категории"
            by_category.setdefault(cat, []).append(r["normalized_query"])

        for cat, queries in by_category.items():
            sample = queries[:5]
            conn.execute(
                """INSERT INTO trends (category, period_start, period_end, signal_count, sample_queries)
                   VALUES (?, ?, ?, ?, ?)""",
                (cat, period_start.isoformat(), period_end.isoformat(), len(queries),
                 json.dumps(sample, ensure_ascii=False)),
            )

    return len(by_category)
