"""
Первичная регистрация источников в БД. Отредактируй под свои реальные значения
(chat-имена, api_id/api_hash, селекторы форума) и запусти один раз:

    python seed_sources.py
"""
from db import db

db.init_db()

# Kufar — раздел "куплю", ключевой запрос можно менять/дублировать под разные ниши
db.upsert_source(
    code="kufar_kuplu",
    name="Kufar: куплю",
    kind="kufar",
    config={"search_query": "куплю", "page_size": 50},
)

# Telegram-чат — ЗАПОЛНИ api_id/api_hash с https://my.telegram.org и имя чата
db.upsert_source(
    code="tg_barahlo_minsk",
    name="TG: барахолка Минск",
    kind="telegram",
    config={
        "api_id": 0,                 # <-- заполнить
        "api_hash": "",              # <-- заполнить
        "session_name": "demand_radar",
        "chat": "@example_chat",     # <-- заполнить реальным username/id чата
        "limit": 200,
    },
    enabled=False,  # включить после заполнения api_id/api_hash
)

# Форум Onliner — селекторы примерные, нужно свериться с реальной вёрсткой раздела
db.upsert_source(
    code="onliner_forum_example",
    name="Onliner Forum (пример раздела)",
    kind="forum_generic",
    config={
        "list_url": "https://forum.onliner.by/viewforum.php?f=REPLACE_ME",
        "post_selector": "div.post",
        "text_selector": ".post-content",
        "author_selector": ".username",
        "link_selector": "a.post-permalink",
    },
    enabled=False,  # включить после проверки селекторов
)

print("Источники зарегистрированы. Проверь/включи их в БД перед первым запуском пайплайна.")
