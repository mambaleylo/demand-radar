"""
Точка входа для полного цикла обработки. Запускать по cron/Termux:Boot, например каждые 2-6 часов:

    python run_pipeline.py collect          # собрать новые сообщения со всех включённых источников
    python run_pipeline.py filter           # прогнать через дешёвый keyword-предфильтр (обе стороны)
    python run_pipeline.py classify         # классифицировать сторону спроса через LLM
    python run_pipeline.py classify_supply  # классифицировать сторону предложения (отдам/дёшево) через LLM
    python run_pipeline.py matches          # показать текущие арбитражные пары спрос+предложение
    python run_pipeline.py trends           # пересчитать недельные тренды
    python run_pipeline.py all              # всё по порядку
"""
import sys
import json
from db import db
from collectors.registry import get_collector
from pipeline.prefilter import looks_like_demand
from pipeline.prefilter_supply import looks_like_supply
from pipeline.classifier import classify_batch, classify_supply_batch
from pipeline.aggregator import build_weekly_trends


def cmd_collect():
    sources = db.get_enabled_sources()
    total_new = 0
    for src in sources:
        config = json.loads(src["config_json"] or "{}")
        try:
            collector = get_collector(src["kind"], config)
        except ValueError as e:
            print(f"[collect] пропуск {src['code']}: {e}")
            continue

        print(f"[collect] {src['code']} ({src.get('signal_type', 'demand')})...")
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
                signal_type=src.get("signal_type", "demand"),
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
    demand_passed = 0
    supply_passed = 0
    for m in messages:
        all_ids.append(m["id"])
        signal_type = m.get("signal_type", "demand")
        if signal_type == "supply":
            ok = looks_like_supply(m["text"])
            if ok:
                supply_passed += 1
        else:
            ok = looks_like_demand(m["text"])
            if ok:
                demand_passed += 1
        if ok:
            passed_ids.append(m["id"])
    db.mark_prefiltered(all_ids, passed_ids)
    print(f"[filter] проверено {len(all_ids)}, прошло фильтр {len(passed_ids)} "
          f"(спрос: {demand_passed}, предложение: {supply_passed})")


def cmd_classify():
    messages = db.get_unclassified_messages(limit=100, signal_type="demand")
    if not messages:
        print("[classify] нечего классифицировать")
        return
    batch = [{"id": m["id"], "text": m["text"]} for m in messages]
    results = classify_batch(batch)
    for r in results:
        db.save_demand_signal(
            raw_message_id=r["raw_message_id"],
            is_demand=r.get("is_demand", False),
            category=r.get("category"),
            normalized_query=r.get("normalized_query"),
            confidence=r.get("confidence", 0.0),
            reasoning=r.get("reasoning", ""),
        )
    demand_count = sum(1 for r in results if r.get("is_demand"))
    print(f"[classify] обработано {len(results)}, найдено сигналов спроса {demand_count}")


def cmd_classify_supply():
    messages = db.get_unclassified_messages(limit=100, signal_type="supply")
    if not messages:
        print("[classify_supply] нечего классифицировать")
        return
    batch = [{"id": m["id"], "text": m["text"]} for m in messages]
    results = classify_supply_batch(batch)
    for r in results:
        db.save_supply_signal(
            raw_message_id=r["raw_message_id"],
            is_giveaway=r.get("is_giveaway", False),
            category=r.get("category"),
            normalized_item=r.get("normalized_item"),
            value_note=r.get("value_note"),
            confidence=r.get("confidence", 0.0),
            reasoning=r.get("reasoning", ""),
        )
    giveaway_count = sum(1 for r in results if r.get("is_giveaway"))
    print(f"[classify_supply] обработано {len(results)}, найдено сигналов предложения {giveaway_count}")


def cmd_trends():
    n = build_weekly_trends()
    print(f"[trends] построено категорий за неделю: {n}")


def cmd_matches():
    matches = db.get_matches(limit=50)
    if not matches:
        print("[matches] пока нет совпадений спроса и предложения по одной категории")
        return
    print(f"[matches] найдено пар: {len(matches)}")
    for m in matches:
        print(f"  [{m['category']}] отдают: {m['supply_item']} ({m['supply_value']}) -> "
              f"ищут: {m['demand_query']}")
        print(f"    отдаёт: {m['supply_url']}")
        print(f"    покупает: {m['demand_url']}")


def cmd_reclassify_failed():
    """Сбрасывает статус классификации для сообщений (обеих сторон), где раньше
    была ошибка API (api_error / classification_parse_error), чтобы classify/
    classify_supply подхватили их заново. Нужно после смены API-провайдера или ключа."""
    reset_total = 0
    with db.get_conn() as conn:
        for table in ("demand_signals", "supply_signals"):
            rows = conn.execute(
                f"SELECT id, raw_message_id FROM {table} "
                f"WHERE reasoning IN ('api_error', 'classification_parse_error')"
            ).fetchall()
            ids = [r["id"] for r in rows]
            msg_ids = [r["raw_message_id"] for r in rows]
            if ids:
                conn.executemany(f"DELETE FROM {table} WHERE id=?", [(i,) for i in ids])
                conn.executemany("UPDATE raw_messages SET classified=0 WHERE id=?", [(i,) for i in msg_ids])
            reset_total += len(msg_ids)
    print(f"[reclassify_failed] сброшено сообщений для повторной классификации: {reset_total}")


if __name__ == "__main__":
    db.init_db()
    action = sys.argv[1] if len(sys.argv) > 1 else "all"

    actions = {
        "collect": cmd_collect,
        "filter": cmd_filter,
        "classify": cmd_classify,
        "classify_supply": cmd_classify_supply,
        "matches": cmd_matches,
        "trends": cmd_trends,
        "reclassify_failed": cmd_reclassify_failed,
    }

    if action == "all":
        cmd_collect()
        cmd_filter()
        cmd_classify()
        cmd_classify_supply()
        cmd_trends()
    elif action in actions:
        actions[action]()
    else:
        print(f"Неизвестная команда: {action}. Доступно: {list(actions.keys())} или all")
