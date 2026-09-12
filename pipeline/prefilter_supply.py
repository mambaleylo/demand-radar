"""
Предфильтр для обратной стороны сделки — люди отдают вещи даром или почти даром.
Аналог prefilter.py, но ищет маркеры giveaway/дешёвой отдачи вместо маркеров спроса.
"""
import re

SUPPLY_PATTERNS = [
    r"\bотдам\b", r"\bотдаю\b", r"\bотдадим\b",
    r"\bдаром\b", r"\bбесплатно\b",
    r"\bв добрые руки\b", r"\bв хорошие руки\b",
    r"\bв дар\b", r"\bприму в дар\b",
    r"\bподарю\b", r"\bподарим\b",
    r"\bзаберите сами\b", r"\bсамовывоз бесплатно\b",
    r"\bпочти даром\b", r"\bза копейки\b",
]

COMPILED = [re.compile(p, re.IGNORECASE) for p in SUPPLY_PATTERNS]

# Явные исключения — не даём "куплю дорого отдам" ложно пройти фильтр как giveaway
NOISE_PATTERNS = [
    re.compile(r"^\s*куплю\b", re.IGNORECASE),
    re.compile(r"^\s*ищу\b", re.IGNORECASE),
]


def looks_like_supply(text: str) -> bool:
    if not text or len(text.strip()) < 5:
        return False
    for noise in NOISE_PATTERNS:
        if noise.match(text):
            return False
    return any(p.search(text) for p in COMPILED)
