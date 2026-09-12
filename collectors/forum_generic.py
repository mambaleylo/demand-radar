"""
Универсальный коллектор для форумов (Onliner Forum и подобные) через requests + BeautifulSoup.
Так как у каждого форума своя вёрстка, конкретные CSS-селекторы задаются в конфиге —
не нужно писать новый Python-класс под каждый форум, достаточно нового source в БД.

Конфиг (config_json в sources), пример:
{
    "list_url": "https://forum.onliner.by/viewforum.php?f=NN",
    "post_selector": "div.post",
    "text_selector": ".post-content",
    "author_selector": ".username",
    "id_attr": "id",
    "link_selector": "a.post-permalink"
}

Ограничение: без JS-рендеринга (для форумов на серверном рендере этого достаточно;
для SPA-форумов на React/Vue понадобится Playwright — отдельный коллектор по тому же
интерфейсу BaseCollector).
"""
import requests
from bs4 import BeautifulSoup
from .base import BaseCollector


class ForumGenericCollector(BaseCollector):
    code = "forum_generic"
    name = "Generic forum"
    kind = "forum"

    def fetch_new(self) -> list[dict]:
        url = self.config["list_url"]
        try:
            resp = requests.get(url, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (compatible; DemandRadarBot/0.1; +personal-research)"
            })
            resp.raise_for_status()
        except Exception as e:
            print(f"[forum_generic] fetch error ({url}): {e}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        posts = soup.select(self.config["post_selector"])

        results = []
        for post in posts:
            text_el = post.select_one(self.config["text_selector"])
            if not text_el:
                continue
            text = text_el.get_text(strip=True, separator=" ")
            if not text:
                continue

            author_el = post.select_one(self.config.get("author_selector", "")) if self.config.get("author_selector") else None
            link_el = post.select_one(self.config.get("link_selector", "")) if self.config.get("link_selector") else None

            ext_id = post.get(self.config.get("id_attr", "id")) or str(hash(text))

            results.append({
                "external_id": str(ext_id),
                "author": author_el.get_text(strip=True) if author_el else None,
                "text": text,
                "url": link_el.get("href") if link_el else url,
                "posted_at": None,
            })
        return results
