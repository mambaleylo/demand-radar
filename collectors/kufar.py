"""
Коллектор Kufar.

ВАЖНО: у Kufar есть публичный (неофициальный) JSON API, который использует сам сайт
(api.kufar.by). Точный путь/параметры периодически меняются, поэтому здесь —
рабочий каркас с понятной точкой замены. Проверить актуальный endpoint проще всего
через DevTools -> Network на kufar.by при поиске по разделу "куплю".

Конфиг (config_json в таблице sources), пример:
{
    "search_query": "куплю шины",
    "category_id": null,
    "region": "minsk"
}
"""
import requests
from datetime import datetime, timezone
from .base import BaseCollector

KUFAR_SEARCH_API = "https://api.kufar.by/search-api/v2/search/rendered-paginated"


class KufarCollector(BaseCollector):
    code = "kufar"
    name = "Kufar"
    kind = "marketplace"

    def fetch_new(self) -> list[dict]:
        query = self.config.get("search_query", "куплю")
        params = {
            "query": query,
            "size": self.config.get("page_size", 50),
            "lang": "ru",
        }
        try:
            resp = requests.get(KUFAR_SEARCH_API, params=params, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (compatible; DemandRadarBot/0.1; +personal-research)"
            })
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[kufar] fetch error: {e}")
            return []

        results = []
        for ad in data.get("ads", []):
            results.append({
                "external_id": str(ad.get("ad_id")),
                "author": ad.get("account_id"),
                "text": ad.get("subject", "") + "\n" + ad.get("body", ""),
                "url": f"https://www.kufar.by/item/{ad.get('ad_id')}",
                "posted_at": ad.get("list_time"),
            })
        return results
