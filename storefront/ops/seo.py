"""Снимок поиска: собрать, сохранить, показать движением.

ОДНА ФУНКЦИЯ СОБИРАЕТ, И ОНА НЕ ПАДАЕТ. Источников два, и любой из них может
молчать: скоуп Вебмастера не выдан, ключ Search API не положен в `.env`, Яндекс
ответил отказом. Падать в этом случае нельзя по двум причинам. Первая: сбор
идёт из утренней сводки, а сводка обязана прийти и без поисковых данных — она
ради денег и воронки, и потерять их из-за одного недоступного источника было бы
обменом не в ту сторону. Вторая: частичный снимок с ЧЕСТНОЙ ПРИЧИНОЙ полезнее
отсутствующего, потому что «неизвестно, потому что не выдан скоуп» — это
инструкция к действию, а пустое место — нет.

ПОЧЕМУ ДВИЖЕНИЕ ВАЖНЕЕ СОСТОЯНИЯ. «В индексе 9 страниц» не отвечает ни на один
вопрос; «9, а вчера было 2» отвечает на все. Поэтому снимки лежат по суткам, и
всякая строка, которую мы показываем, сравнивается с предыдущей записью — либо
явно помечается как «первый замер», чтобы отсутствие стрелки не читалось как
отсутствие движения.
"""

import datetime
import logging
from typing import Any

from ops import seo_api
from ops.models import SeoDay

_log = logging.getLogger("ops.seo")


def collect(day: datetime.date | None = None, *, recrawl: list[str] | None = None) -> SeoDay:
    """Собрать и сохранить снимок за сутки. Исключений не бросает.

    Повторный вызов в тот же день ПЕРЕЗАПИСЫВАЕТ строку: смысл таблицы —
    движение по дням, а не история попыток. Иначе утренний перезапуск сводки
    создавал бы вторую запись за те же сутки, и «вчера» стало бы сегодня.
    """
    day = day or datetime.date.today()
    fields: dict[str, Any] = {
        "pages_in_index": None,
        "pages_in_index_estimate": None,
        "sqi": None,
        "positions": [],
        "popular_queries": [],
        "recrawl": {},
        "sources": {},
    }

    if seo_api.webmaster_configured():
        try:
            summary = seo_api.webmaster_summary()
            fields["pages_in_index"] = summary.get("pages_in_search")
            fields["sqi"] = summary.get("sqi")
            fields["sources"]["webmaster"] = "ok"
        except Exception as error:  # noqa: BLE001 — причина и есть результат
            fields["sources"]["webmaster"] = f"{type(error).__name__}: {error}"
            _log.warning("вебмастер недоступен: %s", error)
        try:
            fields["popular_queries"] = seo_api.webmaster_popular()
        except Exception as error:  # noqa: BLE001
            fields["sources"]["webmaster_queries"] = f"{type(error).__name__}: {error}"
        if recrawl:
            try:
                fields["recrawl"] = seo_api.webmaster_recrawl(recrawl)
            except Exception as error:  # noqa: BLE001
                fields["sources"]["recrawl"] = f"{type(error).__name__}: {error}"
    else:
        fields["sources"]["webmaster"] = "не настроен: нет OAuth-доступа владельца"

    if seo_api.search_configured():
        try:
            fields["pages_in_index_estimate"] = seo_api.search_index_count()
            fields["sources"]["search"] = "ok"
        except Exception as error:  # noqa: BLE001
            fields["sources"]["search"] = f"{type(error).__name__}: {error}"
            _log.warning("Search API недоступен: %s", error)
        try:
            fields["positions"] = seo_api.search_positions(list(seo_api.TARGET_QUERIES))
        except Exception as error:  # noqa: BLE001
            fields["sources"]["positions"] = f"{type(error).__name__}: {error}"
    else:
        fields["sources"]["search"] = "не настроен: нет ключа Search API"

    snapshot, _ = SeoDay.objects.update_or_create(day=day, defaults=fields)
    return snapshot


def _delta(now: int | None, before: int | None) -> str:
    """Стрелка движения. «Первый замер» — это тоже ответ, а не пустое место."""
    if now is None or before is None:
        return ""
    if now == before:
        return " (без изменений)"
    return f" (было {before}, {'+' if now > before else ''}{now - before})"


def in_top10(snapshot: SeoDay) -> int:
    return sum(1 for row in snapshot.positions if row.get("position"))


def digest_lines(snapshot: SeoDay, before: SeoDay | None = None) -> list[str]:
    """Строки для утренней сводки: индекс, позиции, и что именно не ответило."""
    lines: list[str] = []

    if snapshot.pages_in_index is not None:
        lines.append(f"🔍 В индексе: {snapshot.pages_in_index} стр."
                     + _delta(snapshot.pages_in_index,
                              before.pages_in_index if before else None))
    else:
        reason = snapshot.sources.get("webmaster", "нет данных")
        estimate = (f", по оценке site: {snapshot.pages_in_index_estimate}"
                    if snapshot.pages_in_index_estimate is not None else "")
        lines.append(f"🔍 В индексе: нет данных{estimate} — {reason}")

    if snapshot.positions:
        top = in_top10(snapshot)
        lines.append(f"Позиции: {top} из {len(snapshot.positions)} запросов в топ-10"
                     + _delta(top, in_top10(before) if before else None))
    if snapshot.popular_queries:
        names = ", ".join(q.get("query", "") for q in snapshot.popular_queries[:3])
        lines.append(f"Показы есть по: {names}")
    return lines
