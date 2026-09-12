"""
Коллектор Telegram через Telethon (ユーザ-сессия, не бот — так можно читать чаты,
в которых ты уже состоишь, включая барахолки/чаты "куплю-продам").

Требуется один раз:
  pip install telethon
  получить api_id/api_hash на https://my.telegram.org
  первый запуск — интерактивный логин (код из Telegram), сессия сохранится в .session файл

Конфиг (config_json в sources), пример:
{
    "api_id": 123456,
    "api_hash": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "session_name": "demand_radar",
    "chat": "@barahlo_minsk",
    "limit": 200
}
"""
from datetime import datetime
from .base import BaseCollector

try:
    from telethon.sync import TelegramClient
except ImportError:
    TelegramClient = None  # ставится по требованию, см. requirements.txt


class TelegramCollector(BaseCollector):
    code = "telegram"
    name = "Telegram chat/channel"
    kind = "telegram"

    def fetch_new(self) -> list[dict]:
        if TelegramClient is None:
            print("[telegram] Telethon не установлен: pip install telethon")
            return []

        api_id = self.config["api_id"]
        api_hash = self.config["api_hash"]
        session_name = self.config.get("session_name", "demand_radar")
        chat = self.config["chat"]
        limit = self.config.get("limit", 200)

        results = []
        with TelegramClient(session_name, api_id, api_hash) as client:
            for msg in client.iter_messages(chat, limit=limit):
                if not msg.text:
                    continue
                results.append({
                    "external_id": str(msg.id),
                    "author": str(msg.sender_id) if msg.sender_id else None,
                    "text": msg.text,
                    "url": None,
                    "posted_at": msg.date.isoformat() if msg.date else None,
                })
        return results
