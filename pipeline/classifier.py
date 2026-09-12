"""
Классификация сообщений через Google Gemini API (бесплатный тариф) батчами.
Задача модели: по тексту сообщения решить —
  1) это реальный неудовлетворённый спрос (человек ищет товар/услугу, которую не может найти)
     или шум (продажа, отвлечённый разговор, спам)?
  2) если спрос — категория и нормализованная формулировка запроса.

Требуется переменная окружения GEMINI_API_KEY (бесплатный ключ без привязки карты —
https://aistudio.google.com/apikey).

Модель gemini-2.5-flash сейчас на бесплатном тарифе. Google периодически меняет состав
бесплатных моделей — актуальный список смотри на https://ai.google.dev/pricing. Если
модель перестанет быть бесплатной или пропадёт, поменяй значение MODEL ниже.
"""
import os
import json
import requests

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
MODEL = "gemini-2.5-flash"

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
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Не задана переменная окружения GEMINI_API_KEY")

    url = f"{API_BASE}/{MODEL}:generateContent"
    headers = {
        "x-goog-api-key": api_key,
        "content-type": "application/json",
    }
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": text[:2000]}]}],
        "generationConfig": {
            "maxOutputTokens": 300,
            "responseMimeType": "application/json",  # просим модель сразу вернуть чистый JSON
        },
    }

    fallback = {
        "is_demand": False,
        "category": None,
        "normalized_query": None,
        "confidence": 0.0,
        "reasoning": "api_error",
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code >= 400:
            print(f"[classifier] API error {resp.status_code}: {resp.text[:500]}")
            return fallback
        data = resp.json()
        raw = data["candidates"][0]["content"]["parts"][0]["text"].strip()
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
