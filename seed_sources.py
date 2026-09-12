"""
Первичная регистрация источников в БД. Отредактируй под свои реальные значения
(chat-имена, api_id/api_hash, селекторы форума) и запусти:

    python seed_sources.py

(можно запускать повторно — upsert_source обновляет существующие записи по code)
"""
from db import db

db.init_db()

# --- СПРОС (люди ищут купить) ---

# Kufar, раздел "Спрос" — это не текстовый поиск, а отдельная категория объявлений
# (люди ищут/хотят купить). Можно добавить несколько подкатегорий как отдельные источники —
# полный список подкатегорий смотри на https://www.kufar.by/l/r~minsk/spros
db.upsert_source(
    code="kufar_spros_all",
    name="Kufar: Спрос (все категории, Минск)",
    kind="kufar_spros",
    signal_type="demand",
    config={"list_url": "https://www.kufar.by/l/r~minsk/spros?sort=lst.d", "max_pages": 2},
)

# Старый вариант через текстовый поиск не даёт результатов для "спроса" — Kufar не индексирует
# "куплю" как текст, это отдельная категория. Оставлен выключенным для справки/на будущее.
db.upsert_source(
    code="kufar_kuplu_textsearch",
    name="Kufar: текстовый поиск 'куплю' (не работает, см. kufar_spros)",
    kind="kufar",
    signal_type="demand",
    config={"search_query": "куплю", "page_size": 50},
    enabled=False,
)

# --- ПРЕДЛОЖЕНИЕ (отдают даром/дёшево) ---

# У Kufar нет отдельной рубрики "Отдам даром" по тому же принципу, что "Спрос" —
# такие объявления разбросаны по обычным категориям. Поэтому берём общую ленту
# по всем категориям Минска (новые объявления) и отсеиваем giveaway-маркеры
# ("отдам", "даром", "бесплатно" и т.п.) уже на этапе prefilter_supply.py.
# Коллектор тот же самый (kufar_spros — просто HTML-скрейпер по /item/ссылкам),
# просто указывает на другой URL.
db.upsert_source(
    code="kufar_giveaway_all",
    name="Kufar: вся лента (Минск, поиск giveaway-маркеров)",
    kind="kufar_spros",
    signal_type="supply",
    config={"list_url": "https://www.kufar.by/l/r~minsk?sort=lst.d", "max_pages": 3},
)

# Telegram-чат — ЗАПОЛНИ api_id/api_hash с https://my.telegram.org и имя чата
# Один и тот же чат может быть источником и спроса, и предложения одновременно —
# для этого просто зарегистрируй его дважды с разными code/signal_type.
db.upsert_source(
    code="tg_barahlo_minsk",
    name="TG: барахолка Минск",
    kind="telegram",
    signal_type="demand",
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
    signal_type="demand",
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
