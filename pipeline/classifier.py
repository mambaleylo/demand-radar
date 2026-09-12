"""
Классификация сообщений через OpenRouter (бесплатные модели) батчами.
Две стороны сделки классифицируются отдельными промптами, но одним и тем же
списком категорий (см. categories.py), чтобы их потом можно было сводить в matcher.py:
  - classify_message / classify_batch — спрос (человек ищет купить)
  - classify_supply_message / classify_supply_batch — предложение (отдают даром/дёшево)

Требуется переменная окружения OPENROUTER_API_KEY (бесплатный ключ без карты —
https://openrouter.ai/keys).

Список бесплатных моделей у OpenRouter меняется без предупреждения (модели то
появляются, то становятся платными) — актуальный список: openrouter.ai/models
(фильтр price: free), обновить DEFAULT_MODELS ниже при необходимости.
"""
import os
import json
import requests

from .categories import CATEGORY_LIST_TEXT

API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Проверено вживую на openrouter.ai/api/v1/models (сентябрь 2026) — модели с
# pricing prompt=0 и completion=0, общего назначения. OpenRouter сам перебирает
# список по порядку, если модель недоступна/перегружена. Максимум 3 элемента —
# ограничение самого OpenRouter на размер поля "models".
DEFAULT_MODELS = [
    "nex-agi/nex-n2.5-pro:free",
    "thinkingmachines/inkling-small:free",
    "nvidia/nemotron-3.5-lightning:free",
]

DEMAND_SYSTEM_PROMPT = f"""Ты анализируешь сообщения с форумов/досок объявлений/чатов в Беларуси,
чтобы найти сигналы неудовлетворённого спроса — случаи, когда человек ищет товар или услугу,
которую не может найти, и это похоже на рыночную возможность.

Категория ДОЛЖНА быть одной из этого списка: [{CATEGORY_LIST_TEXT}]. Если ничего не подходит — "Другое".

Для каждого сообщения верни STRICT JSON (без markdown, без пояснений вне JSON):
{{
  "is_demand": true/false,
  "category": "одна из категорий списка выше или null",
  "normalized_query": "нормализованная формулировка запроса, например 'ищет: зимние шины 205/55 R16' или null",
  "confidence": 0.0-1.0,
  "reasoning": "одно короткое предложение почему"
}}

is_demand=false если: это объявление о продаже, обсуждение без явного запроса,
жалоба без поиска альтернативы, спам, флуд, или запрос слишком общий чтобы быть полезным сигналом.
Отвечай ТОЛЬКО валидным JSON, без markdown-обрамления вроде ```json.
"""

SUPPLY_SYSTEM_PROMPT = f"""Ты анализируешь сообщения с форумов/досок объявлений/чатов в Беларуси,
чтобы найти сигналы предложения — случаи, когда человек отдаёт вещь даром, почти даром или очень
дёшево (не обычная продажа по рыночной цене, а именно избавление от вещи с минимальной выгодой).

Категория ДОЛЖНА быть одной из этого списка: [{CATEGORY_LIST_TEXT}]. Если ничего не подходит — "Другое".

Для каждого сообщения верни STRICT JSON (без markdown, без пояснений вне JSON):
{{
  "is_giveaway": true/false,
  "category": "одна из категорий списка выше или null",
  "normalized_item": "краткое описание вещи, например 'отдаёт: старый платяной шкаф' или null",
  "value_note": "'бесплатно' | 'почти даром' | конкретная цена если указана, или null",
  "confidence": 0.0-1.0,
  "reasoning": "одно короткое предложение почему"
}}

is_giveaway=false если: это обычная продажа по рыночной цене, спрос ("куплю"/"ищу"), спам,
флуд, или объявление слишком общее чтобы быть полезным сигналом.
Отвечай ТОЛЬКО валидным JSON, без markdown-обрамления вроде ```json.
"""


def _get_models() -> list[str]:
    override = os.environ.get("OPENROUTER_MODELS")
    if override:
        models = [m.strip() for m in override.split(",") if m.strip()]
    else:
        models = DEFAULT_MODELS
    return models[:3]  # OpenRouter: models array must have 3 items or fewer


def _call_llm(system_prompt: str, text: str, fallback: dict) -> dict:
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
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text[:2000]},
        ],
        # Модели в списке — reasoning-модели: часть токенов уходит на внутренние
        # рассуждения до финального ответа. При малом max_tokens ответ обрезается
        # до пустой строки, поэтому лимит с запасом.
        "max_tokens": 1024,
    }

    try:
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        if resp.status_code >= 400:
            print(f"[classifier] API error {resp.status_code}: {resp.text[:500]}")
            return dict(fallback)
        data = resp.json()
        raw = (data["choices"][0]["message"].get("content") or "").strip()
        if not raw:
            print(f"[classifier] пустой ответ модели, полный payload ответа: {str(data)[:500]}")
            return dict(fallback)
    except Exception as e:
        print(f"[classifier] API error: {e}")
        return dict(fallback)

    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        result = dict(fallback)
        result["reasoning"] = "classification_parse_error"
        return result


def classify_message(text: str) -> dict:
    fallback = {
        "is_demand": False,
        "category": None,
        "normalized_query": None,
        "confidence": 0.0,
        "reasoning": "api_error",
    }
    return _call_llm(DEMAND_SYSTEM_PROMPT, text, fallback)


def classify_supply_message(text: str) -> dict:
    fallback = {
        "is_giveaway": False,
        "category": None,
        "normalized_item": None,
        "value_note": None,
        "confidence": 0.0,
        "reasoning": "api_error",
    }
    return _call_llm(SUPPLY_SYSTEM_PROMPT, text, fallback)


def classify_batch(messages: list[dict]) -> list[dict]:
    """messages: список словарей с ключами id, text. Возвращает список результатов с тем же id."""
    results = []
    for msg in messages:
        result = classify_message(msg["text"])
        result["raw_message_id"] = msg["id"]
        results.append(result)
    return results


def classify_supply_batch(messages: list[dict]) -> list[dict]:
    results = []
    for msg in messages:
        result = classify_supply_message(msg["text"])
        result["raw_message_id"] = msg["id"]
        results.append(result)
    return results
