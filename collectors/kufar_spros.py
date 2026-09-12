"""
Коллектор раздела "Спрос" на Kufar — это отдельная категория объявлений
(люди ищут/хотят купить), адресуется через путь в URL, а не через query-параметр:

  https://www.kufar.by/l/r~minsk/spros                          — весь раздел "Спрос" по Минску
  https://www.kufar.by/l/r~minsk/spros-avto-i-transport         — подкатегория "Авто и транспорт"
  https://www.kufar.by/l/r~minsk/spros-bytovaya-tehnika         — подкатегория "Бытовая техника"
  ...и т.д. (полный список подкатегорий смотри на самой странице /l/r~minsk/spros)

Страница отдаётся сервером с готовым HTML (без обязательного JS), поэтому парсим
через requests + BeautifulSoup. Чтобы не зависеть от конкретных CSS-классов (они
могут поменяться при редизайне), извлекаем объявления по структурному признаку —
любая ссылка вида /item/<id>, где <id> — числовой ID объявления. Это устойчивее,
чем полагаться на названия классов.

Конфиг (config_json в sources), пример:
{
    "list_url": "https://www.kufar.by/l/r~minsk/spros-avto-i-transport?sort=lst.d",
    "max_pages": 2
}
"""
import re
import requests
from bs4 import BeautifulSoup
from .base import BaseCollector

ITEM_HREF_RE = re.compile(r"/item/(\d+)")


class KufarSprosCollector(BaseCollector):
    code = "kufar_spros"
    name = "Kufar: раздел Спрос"
    kind = "kufar_spros"

    def fetch_new(self) -> list[dict]:
        base_url = self.config["list_url"]
        max_pages = self.config.get("max_pages", 1)

        results = []
        seen_ids = set()

        for page in range(1, max_pages + 1):
            url = base_url
            if page > 1:
                sep = "&" if "?" in base_url else "?"
                url = f"{base_url}{sep}page={page}"

            try:
                resp = requests.get(url, timeout=15, headers={
                    "User-Agent": "Mozilla/5.0 (compatible; DemandRadarBot/0.1; +personal-research)"
                })
                resp.raise_for_status()
            except Exception as e:
                print(f"[kufar_spros] fetch error ({url}): {e}")
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            page_had_items = False

            for a in soup.find_all("a", href=True):
                m = ITEM_HREF_RE.search(a["href"])
                if not m:
                    continue
                item_id = m.group(1)
                if item_id in seen_ids:
                    continue
                seen_ids.add(item_id)

                text = a.get_text(strip=True, separator=" ")
                if not text:
                    continue

                page_had_items = True
                full_url = a["href"] if a["href"].startswith("http") else f"https://www.kufar.by{a['href']}"
                results.append({
                    "external_id": item_id,
                    "author": None,
                    "text": text,
                    "url": full_url,
                    "posted_at": None,
                })

            if not page_had_items:
                break  # дальше пустые страницы, нет смысла продолжать

        return results
