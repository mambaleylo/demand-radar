"""
Первичная регистрация источников в БД. Отредактируй под свои реальные значения
(chat-имена, api_id/api_hash, селекторы форума) и запусти один раз:

    python seed_sources.py
"""
from db import db

db.init_db()

# Kufar, раздел "Спрос" — это не текстовый поиск, а отдельная категория объявлений
# (люди ищут/хотят купить). Можно добавить несколько подкатегорий как отдельные источники —
# полный список подкатегорий смотри на https://www.kufar.by/l/r~minsk/spros
db.upsert_source(
    code="kufar_spros_all",
    name="Kufar: Спрос (все категории, Минск)",
    kind="kufar_spros",
    config={"list_url": "https://www.kufar.by/l/r~minsk/spros?sort=lst.d", "max_pages": 2},
)

# Старый вариант через текстовый поиск не даёт результатов для "спроса" — Kufar не индексирует
# "куплю" как текст, это отдельная категория. Оставлен выключенным для справки/на будущее.
db.upsert_source(
    code="kufar_kuplu_textsearch",
    name="Kufar: текстовый поиск 'куплю' (не работает, см. kufar_spros)",
    kind="kufar",
    config={"search_query": "куплю", "page_size": 50},
    enabled=False,
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
