"""
Классификация сообщений через Claude API батчами.
Задача модели: по тексту сообщения решить —
  1) это реальный неудовлетворённый спрос (человек ищет товар/услугу, которую не может найти)
     или шум (продажа, отвлечённый разговор, спам)?
  2) если спрос — категория и нормализованная формулировка запроса.

Требуется переменная окружения ANTHROPIC_API_KEY.

Намеренно без пакета `anthropic` (SDK): его зависимость `jiter` собирается из Rust
и на Termux/Android часто не ставится (нет Rust-тулчейна из коробки). Вместо этого —
прямой HTTP-запрос через requests, который уже используется в остальном проекте.
"""
import os
import json
import requests

API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

# Haiku — дешёвая и быстрая модель, подходит для массовой классификации коротких сообщений.
# Если качество классификации будет хромать — поменять на "claude-sonnet-5".
MODEL = "claude-haiku-4-5-20251001"

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
"""


def classify_message(text: str) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("Не задана переменная окружения ANTHROPIC_API_KEY")

    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    payload = {
        "model": MODEL,
        "max_tokens": 300,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": text[:2000]}],
    }

    try:
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        raw = data["content"][0]["text"].strip()
    except Exception as e:
        print(f"[classifier] API error: {e}")
        return {
            "is_demand": False,
            "category": None,
            "normalized_query": None,
            "confidence": 0.0,
            "reasoning": "api_error",
        }

    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "is_demand": False,
            "category": None,
            "normalized_query": None,
            "confidence": 0.0,
            "reasoning": "classification_parse_error",
        }


def classify_batch(messages: list[dict]) -> list[dict]:
    """messages: список словарей с ключами id, text. Возвращает список результатов с тем же id."""
    results = []
    for msg in messages:
        result = classify_message(msg["text"])
        result["raw_message_id"] = msg["id"]
        results.append(result)
    return results
