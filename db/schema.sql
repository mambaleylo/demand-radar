-- demand-radar schema
-- SQLite by default (пере-скомпилируется в Postgres при масштабировании — см. db.py)

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,          -- 'kufar', 'tg:barahlo_minsk', 'onliner_forum'
    name TEXT NOT NULL,
    kind TEXT NOT NULL,                 -- 'marketplace' | 'telegram' | 'forum' | 'other'
    signal_type TEXT DEFAULT 'demand',  -- 'demand' (люди ищут купить) | 'supply' (отдают дёшево/даром)
    enabled INTEGER DEFAULT 1,
    config_json TEXT,                   -- произвольный конфиг коллектора (url, chat_id, селекторы...)
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    external_id TEXT NOT NULL,          -- id сообщения/поста на площадке (для дедупа)
    author TEXT,
    text TEXT NOT NULL,
    url TEXT,
    posted_at TEXT,
    signal_type TEXT DEFAULT 'demand',  -- скопировано из sources.signal_type на момент сбора,
                                         -- чтобы filter/classify знали какой пайплайн применять
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP,
    prefiltered INTEGER DEFAULT 0,      -- прошло ли через keyword-фильтр (1/0)
    classified INTEGER DEFAULT 0,       -- прошло ли через LLM (1/0)
    UNIQUE(source_id, external_id)
);

CREATE TABLE IF NOT EXISTS demand_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_message_id INTEGER NOT NULL REFERENCES raw_messages(id),
    is_demand INTEGER NOT NULL,         -- 1 если LLM решил, что это реальный неудовлетворённый спрос
    category TEXT,                      -- категория товара/услуги (из общего списка категорий Kufar)
    normalized_query TEXT,              -- краткая нормализованная формулировка запроса ("ищет: зимние шины 205/55 R16")
    confidence REAL,
    reasoning TEXT,                     -- краткое обоснование LLM (для отладки/доверия)
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Обратная сторона сделки: люди отдают даром/дёшево. Та же структура что и
-- demand_signals, чтобы обе стороны можно было свести по одинаковой категории.
CREATE TABLE IF NOT EXISTS supply_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_message_id INTEGER NOT NULL REFERENCES raw_messages(id),
    is_giveaway INTEGER NOT NULL,       -- 1 если LLM решил, что это реальная отдача даром/почти даром
    category TEXT,                      -- категория товара (из того же списка, что и demand_signals)
    normalized_item TEXT,               -- краткое описание, например "отдаёт: старый платяной шкаф"
    value_note TEXT,                    -- 'бесплатно' | 'почти даром' | 'договорная' | конкретная цена
    confidence REAL,
    reasoning TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    period_start TEXT NOT NULL,         -- начало недели/месяца
    period_end TEXT NOT NULL,
    signal_count INTEGER NOT NULL,
    sample_queries TEXT,                -- JSON-массив примеров запросов
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Заготовка под будущий SaaS: пользователи и сохранённые ниши/отчёты
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    plan TEXT DEFAULT 'free',           -- 'free' | 'pro' | 'business'
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS saved_watches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    keyword_or_category TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
