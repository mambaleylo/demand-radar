"""
Предфильтр: дешёвая эвристика, чтобы не гонять через LLM всё подряд.
Ищем маркеры неудовлетворённого спроса на русском/белорусском в бытовой лексике.
Это грубый фильтр "может быть спрос" — окончательное решение принимает LLM в classifier.py.
"""
import re

DEMAND_PATTERNS = [
    r"\bищу\b", r"\bищем\b",
    r"\bкуплю\b", r"\bкупил бы\b",
    r"\bнужен\b", r"\bнужна\b", r"\bнужны\b", r"\bнужно\b",
    r"\bпосоветуйте\b", r"\bпосоветуй\b",
    r"\bгде найти\b", r"\bгде купить\b", r"\bгде взять\b",
    r"\bкто продаёт\b", r"\bкто продает\b",
    r"\bнет в наличии\b", r"\bнигде нет\b", r"\bне могу найти\b",
    r"\bподскажите.{0,20}(где|кто|как)\b",
    r"\bищу мастера\b", r"\bищу специалиста\b",
    r"\bкто делает\b", r"\bкто занимается\b",
]

COMPILED = [re.compile(p, re.IGNORECASE) for p in DEMAND_PATTERNS]

# Явные исключения — снижают шум от объявлений "продаю" (обратный сигнал, не нужен)
NOISE_PATTERNS = [
    re.compile(r"^\s*продам\b", re.IGNORECASE),
    re.compile(r"^\s*продаю\b", re.IGNORECASE),
]


def looks_like_demand(text: str) -> bool:
    if not text or len(text.strip()) < 5:
        return False
    for noise in NOISE_PATTERNS:
        if noise.match(text):
            return False
    return any(p.search(text) for p in COMPILED)
