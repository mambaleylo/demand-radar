"""
Классификация сообщений через OpenRouter (бесплатные модели) батчами.
Задача модели: по тексту сообщения решить —
  1) это реальный неудовлетворённый спрос (человек ищет товар или услугу, которую не может найти)
     или шум (продажа, отвлечённый разговор, спам)?
  2) если спрос — категория и нормализованная формулировка запроса.

Требуется переменная окружения OPENROUTER_API_KEY (бесплатный ключ без карты —
https://openrouter.ai/keys).

OpenRouter периодически меняет состав бесплатных моделей (см. openrouter.ai/models,
фильтр "free"). Поэтому здесь список из нескольких кандидатов через запятую в
OPENROUTER_MODELS — если первая модель недоступна/перегружена, OpenRouter сам
пробует следующую по списку (встроенный fallback через поле "models").
Если ни одна модель из дефолтного списка не работает — обнови DEFAULT_MODELS
актуальными :free ID со страницы openrouter.ai/models.
"""
import os
import json
import requests

API_URL = "https://openrouter.ai/api/v1/chat/completions"

DEFAULT_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen-2.5-72b-instruct:free",
    "google/gemma-2-9b-it:free",
]

SYSTEM_PROMPT = """Ты анализируешь сообщения с форумов/досок объявлений/чатов в Беларуси,
чтобы найти сигналы неудовлетворённого спроса — случаи, когда человек ищет товар или услугу,
которую не может найти, и это похоже на рыночную возможность.

Для каждого сообщения верни STRICT JSON (без markdown, без пояснений вне JSON):
{
  "is_demand": true/false,
  "category": "краткая категория товара/услуги на русском или null",
  "normalized_query": "нормализованная формулировка запроса, например 'ищет: зимние шины 205/55 R16' или null",
  "confidence": 0.0-1.0,
  "reasoning": "одно короткое предложение почему"
}

is_demand=false если: это объявление о продаже, обсуждение без явного запроса,
жалоба без поиска альтернативы, спам, флуд, или запрос слишком общий чтобы быть полезным сигналом.
Отвечай ТОЛЬКО валидным JSON, без markdown-обрамления вроде ```json.
"""


def _get_models() -> list[str]:
    override = os.environ.get("OPENROUTER_MODELS")
    if override:
        return [m.strip() for m in override.split(",") if m.strip()]
    return DEFAULT_MODELS


def classify_message(text: str) -> dict:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("Не задана переменная окружения OPENROUTER_API_KEY")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/mambaleylo/demand-radar",
        "X-Title": "Demand Radar",
    }
    payload = {
        "models": _get_models(),  # OpenRouter сам перебирает список при недоступности модели
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text[:2000]},
        ],
        "max_tokens": 300,
    }

    fallback = {
        "is_demand": False,
        "category": None,
        "normalized_query": None,
        "confidence": 0.0,
        "reasoning": "api_error",
    }

    try:
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        if resp.status_code >= 400:
            print(f"[classifier] API error {resp.status_code}: {resp.text[:500]}")
            return fallback
        data = resp.json()
        raw = data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[classifier] API error: {e}")
        return fallback

    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        fallback["reasoning"] = "classification_parse_error"
        return fallback


def classify_batch(messages: list[dict]) -> list[dict]:
    """messages: список словарей с ключами id, text. Возвращает список результатов с тем же id."""
    results = []
    for msg in messages:
        result = classify_message(msg["text"])
        result["raw_message_id"] = msg["id"]
        results.append(result)
    return results
