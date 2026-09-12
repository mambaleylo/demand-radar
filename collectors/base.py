"""
Базовый класс коллектора. Любой новый источник (доска, форум, TG-канал, маркетплейс)
реализует один метод fetch_new() -> list[dict], остальное (сохранение в БД, дедуп)
делает pipeline автоматически.
"""
from abc import ABC, abstractmethod


class BaseCollector(ABC):
    code: str = "base"
    name: str = "Base collector"
    kind: str = "other"

    def __init__(self, config: dict):
        self.config = config or {}

    @abstractmethod
    def fetch_new(self) -> list[dict]:
        """
        Возвращает список новых сообщений в формате:
        {
            "external_id": str,   # уникальный id на площадке
            "author": str | None,
            "text": str,
            "url": str | None,
            "posted_at": str | None,  # ISO-строка, если известна
        }
        """
        raise NotImplementedError
