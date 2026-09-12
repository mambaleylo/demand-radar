"""
Точка входа для полного цикла обработки. Запускать по cron/Termux:Boot, например каждые 2-6 часов:

    python run_pipeline.py collect     # собрать новые сообщения со всех включённых источников
    python run_pipeline.py filter      # прогнать через дешёвый keyword-предфильтр
    python run_pipeline.py classify    # прогнать отфильтрованное через LLM
    python run_pipeline.py trends      # пересчитать недельные тренды
    python run_pipeline.py all         # всё по порядку
"""
import sys
from db import db
from collectors.registry import get_collector
from pipeline.prefilter import looks_like_demand
from pipeline.classifier import classify_batch
from pipeline.aggregator import build_weekly_trends


def cmd_collect():
    sources = db.get_enabled_sources()
    total_new = 0
    for src in sources:
        import json
        config = json.loads(src["config_json"] or "{}")
        try:
            collector = get_collector(src["kind"], config)
        except ValueError as e:
            print(f"[collect] пропуск {src['code']}: {e}")
            continue

        print(f"[collect] {src['code']}...")
        items = collector.fetch_new()
        new_count = 0
        for item in items:
            row_id = db.insert_raw_message(
                source_id=src["id"],
                external_id=item["external_id"],
                author=item.get("author"),
                text=item["text"],
                url=item.get("url"),
                posted_at=item.get("posted_at"),
            )
            if row_id:
                new_count += 1
        print(f"[collect] {src['code']}: +{new_count} новых сообщений")
        total_new += new_count
    print(f"[collect] итого новых: {total_new}")


def cmd_filter():
    messages = db.get_unfiltered_messages(limit=1000)
    passed_ids = []
    all_ids = []
    for m in messages:
        all_ids.append(m["id"])
        if looks_like_demand(m["text"]):
            passed_ids.append(m["id"])
    db.mark_prefiltered(all_ids, passed_ids)
    print(f"[filter] проверено {len(all_ids)}, прошло фильтр {len(passed_ids)}")


def cmd_classify():
    messages = db.get_unclassified_messages(limit=100)
    if not messages:
        print("[classify] нечего классифицировать")
        return
    batch = [{"id": m["id"], "text": m["text"]} for m in messages]
    results = classify_batch(batch)
    for r in results:
        db.save_demand_signal(
            raw_message_id=r["raw_message_id"],
            is_demand=r["is_demand"],
            category=r.get("category"),
            normalized_query=r.get("normalized_query"),
            confidence=r.get("confidence", 0.0),
            reasoning=r.get("reasoning", ""),
        )
    demand_count = sum(1 for r in results if r["is_demand"])
    print(f"[classify] обработано {len(results)}, найдено сигналов спроса {demand_count}")


def cmd_trends():
    n = build_weekly_trends()
    print(f"[trends] построено категорий за неделю: {n}")


def cmd_reclassify_failed():
    """Сбрасывает статус классификации для сообщений, где раньше была ошибка API
    (api_error / classification_parse_error), чтобы classify подхватил их заново.
    Нужно после смены API-провайдера или ключа, если старые попытки сохранились как
    'обработано', хотя реального ответа модели не было."""
    import json as _json
    with db.get_conn() as conn:
        rows = conn.execute(
            """SELECT ds.id, ds.raw_message_id FROM demand_signals ds
               WHERE ds.reasoning IN ('api_error', 'classification_parse_error')"""
        ).fetchall()
        ids = [r["id"] for r in rows]
        msg_ids = [r["raw_message_id"] for r in rows]
        if ids:
            conn.executemany("DELETE FROM demand_signals WHERE id=?", [(i,) for i in ids])
            conn.executemany("UPDATE raw_messages SET classified=0 WHERE id=?", [(i,) for i in msg_ids])
    print(f"[reclassify_failed] сброшено сообщений для повторной классификации: {len(msg_ids)}")


if __name__ == "__main__":
    db.init_db()
    action = sys.argv[1] if len(sys.argv) > 1 else "all"

    actions = {
        "collect": cmd_collect,
        "filter": cmd_filter,
        "classify": cmd_classify,
        "trends": cmd_trends,
        "reclassify_failed": cmd_reclassify_failed,
    }

    if action == "all":
        cmd_collect()
        cmd_filter()
        cmd_classify()
        cmd_trends()
    elif action in actions:
        actions[action]()
    else:
        print(f"Неизвестная команда: {action}. Доступно: {list(actions.keys())} или all")
