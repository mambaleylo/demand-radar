"""
Реестр коллекторов. Чтобы добавить новый источник:
1. Написать класс, унаследованный от BaseCollector (или переиспользовать forum_generic
   для любого сервер-рендеренного форума/доски — тогда новый код вообще не нужен).
2. Зарегистрировать его здесь по kind.
3. Добавить строку в таблицу sources (db.upsert_source) с нужным config_json.

Кандидаты "на потом" (не реализовано, но встраивается по этому же интерфейсу):
- Instagram/Facebook Marketplace (нужен Playwright + логин, ToS жёстче)
- VK группы "барахолка"/"куплю-продам" (есть официальный VK API, проще всего из всех)
- Avito-подобные локальные доски объявлений
- Reddit-аналоги / vc.ru для B2B-спроса
- Отзовики (otzovik и т.п.) — люди жалуются на отсутствие товара/сервиса
"""
from .kufar import KufarCollector
from .kufar_spros import KufarSprosCollector
from .telegram_collector import TelegramCollector
from .forum_generic import ForumGenericCollector

COLLECTOR_REGISTRY = {
    "kufar": KufarCollector,               # текстовый поиск через API — оставлен, но не даёт
                                            # результатов для "спроса" (см. kufar_spros)
    "kufar_spros": KufarSprosCollector,    # рабочий вариант: парсинг раздела "Спрос"
    "telegram": TelegramCollector,
    "forum_generic": ForumGenericCollector,
}


def get_collector(kind: str, config: dict):
    cls = COLLECTOR_REGISTRY.get(kind)
    if not cls:
        raise ValueError(f"Неизвестный тип коллектора: {kind}")
    return cls(config)
