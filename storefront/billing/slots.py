"""Слоты тарифа для экранов: занятость — ЧИСЛОМ, состояние слота — словом.

ПОЧЕМУ ЭТО ОТДЕЛЬНЫЙ МОДУЛЬ. Один и тот же ответ `/admin/instances` читают два
экрана с разными читателями — кабинет клиента и консоль поддержки, — и когда-то
каждый выводил занятость сам: кабинет длиной списка, консоль зелёной плашкой на
всём, что не «остывает». Обе догадки стали враньём в один день. Занятость
считает лицензионный сервер — та же функция, что принимает решение, — а витрина
обязана её ПОКАЗАТЬ, а не вывести заново.

ЧТО ИЗМЕНИЛОСЬ ВМЕСТЕ С СЕРВЕРОМ, И ПОЧЕМУ ЭКРАН ЕДЕТ ОДНИМ РЕЛИЗОМ С НИМ.
Раньше ответ был списком КОНТЕЙНЕРОВ с состояниями `active` / `silent` /
`released` / `reclaimed` — то есть суждением о том, жив ли контейнер. Такого
суждения сервер вынести не может (Chandra–Toueg: детектор отказов нереализуем),
и шесть заходов доказали это на живых клиентах. Теперь ответ — список СЛОТОВ,
каждый со своим держателем и со списком доцеживающих поколений. Состояний
`silent`, `reclaimed`, полей `held_places`, `live_processes`, `turnover_*`,
`alive_seconds` нет ни в ответе, ни здесь: механизмов, которые их считали, нет
тоже. Экран, врущий о том, кто держит слот, и есть дефект (Б26bis) — поэтому
витрина и сервер едут ОДНИМ платформенным релизом.

ТРИ ПРАВИЛА, КОТОРЫЕ ЗДЕСЬ НЕЛЬЗЯ НАРУШАТЬ, И ВСЕ ТРИ КУПЛЕНЫ ДОРОГО:

1. **Занятость — поле сервера, а не длина списка.** В списке есть и свободные
   слоты: считать по нему занятость значило бы всегда показывать число, равное
   тарифу.
2. **Число, которого сервер не назвал, — не ноль.** «0 из 1 занято» при живых
   арендах и «процессов 0» у контейнера с тридцатью двумя воркерами — это оба
   раза ноль, прочитанный человеком как ОТВЕТ. Отсутствующее поле доезжает как
   `None`, и экран пишет «неизвестно».
3. **Слово рядом с числом не противоречит числу.** Экран писал «слот уже
   свободен, поднимайте новый» в той же строке, где стояло «мест занято 32».
   Поэтому `pill` и `note` собираются ЗДЕСЬ, из одних и тех же полей, и оба
   экрана печатают готовое: кабинет и консоль не могут разойтись в словах об
   одном слоте, потому что слова у них одни.
"""


def ago(seconds: float) -> str:
    """Срок словами: «41 с», «12 мин», «3 ч».

    ТА ЖЕ ШКАЛА, ЧТО В ОТКАЗЕ. Строку «слышали 12 мин назад» клиент сперва
    видит в отказе своего контейнера (`licensing/store.py::ago`), а следом — в
    кабинете; разные округления в двух местах читались бы как разные данные.
    Шесть строк дублируются намеренно: витрина не имеет права импортировать
    движок, и общая библиотека ради форматирования завела бы эту зависимость.
    """
    seconds = max(0.0, seconds)
    if seconds < 90:
        return f"{int(seconds)} с"
    if seconds < 5400:
        return f"{int(seconds // 60)} мин"
    return f"{int(seconds // 3600)} ч"


def _number(raw: dict, key: str) -> int | None:
    """Целое поле сервера — или `None`, если сервер его не назвал.

    `raw.get(key, 0)` превращало молчание в число, и именно так на экран
    попадали «0 занято» и «процессов 0» про работающие контейнеры. Молчание
    обязано доезжать молчанием; решает, что с ним делать, экран.
    """
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def _moment(raw: dict, key: str) -> float | None:
    """Отметка времени сервера, или `None`. Ноль — это «не было», а не 1970 год:
    сервер пишет ноль в `last_heard_at` слота, которого ещё никто не занимал."""
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) or None


_FENCE_WORDS = {"claim": "пришёл новый запуск", "admin": "освободила поддержка",
                "plan": "слот выведен сменой тарифа"}


def _draining(rows: object, now: float) -> list[dict]:
    """Поколения, которые слот уже потеряли и доцеживают купленное.

    ЭТО НЕ «ОСТАНОВЛЕННЫЕ КОНТЕЙНЕРЫ», и подписывать их так нельзя. Сервер про
    них знает ровно одно: они больше НЕ ПОКУПАЮТ ёмкость. Работают ли они ещё —
    ненаблюдаемо, поэтому остаток называется оценкой сверху и словом «до».
    """
    out: list[dict] = []
    if not isinstance(rows, list):
        return out
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        fenced_at = _moment(raw, "fenced_at")
        out.append({
            "start_id": str(raw.get("start_id", "") or "")[:16],
            "epoch": _number(raw, "epoch"),
            "fenced_ago": ago(now - fenced_at) if fenced_at else "",
            "fenced_by": _FENCE_WORDS.get(str(raw.get("fenced_by", "") or ""), ""),
            "band_left": _number(raw, "band_left_estimate"),
        })
    return out


def _slot(raw: dict, now: float) -> dict:
    """Одна строка списка слотов, готовая к показу — с плашкой и пояснением.

    ПЛАШКА СОБИРАЕТСЯ ЗДЕСЬ, А НЕ В ШАБЛОНЕ. Два шаблона выводили её сами и
    писали про один и тот же контейнер «ОСТАНОВЛЕН» и «ОТПУЩЕН»; поддержка и
    клиент обязаны видеть одно слово, а различаться должно ОБЪЯСНЕНИЕ рядом.
    """
    holder = raw.get("holder") if isinstance(raw.get("holder"), dict) else None
    draining = _draining(raw.get("draining"), now)
    slot_no = _number(raw, "slot_no")
    epoch = _number(raw, "epoch")
    if holder is None:
        return {"slot_no": slot_no, "epoch": epoch, "held": False,
                "pill": "СВОБОДЕН", "pill_class": "",
                "start_id": "", "installation_id": "", "engine_version": "",
                "since_ago": "", "heard_ago": "", "purchase_ago": "",
                "workers_heard": None, "note": "свободен", "draining": draining}
    heard = _moment(holder, "last_heard_at")
    purchase = _moment(holder, "last_purchase_at")
    since = _moment(holder, "since")
    workers = _number(holder, "workers_heard")
    # ДВА РАЗНЫХ «СЛЫШАЛИ», И ВТОРОЕ СИЛЬНЕЕ ПЕРВОГО. Отметку двигает любое
    # сообщение; ПОКУПКУ ёмкости делает только тот, кто собирается обслуживать.
    # Поэтому строка про покупку стоит отдельно: она — нижняя граница «живых»,
    # единственная, которую теорема нам оставляет.
    note = f"поколение {epoch}"
    if since:
        note += f" с {ago(now - since)} назад"
    if holder.get("engine_version"):
        note += f" · движок {holder['engine_version']}"
    if workers is None:
        note += " · воркеров сервер не назвал"
    else:
        note += f" · воркеров слышно {workers}"
    note += (f" · ёмкость покупал {ago(now - purchase)} назад" if purchase
             else " · ёмкость ещё не покупал")
    return {"slot_no": slot_no, "epoch": epoch, "held": True,
            "pill": "ЗАНЯТ", "pill_class": "ok",
            "start_id": str(holder.get("start_id", "") or "")[:16],
            "installation_id": str(holder.get("installation_id", "") or ""),
            "engine_version": str(holder.get("engine_version", "") or ""),
            "since_ago": ago(now - since) if since else "",
            "heard_ago": ago(now - heard) if heard else "",
            "purchase_ago": ago(now - purchase) if purchase else "",
            "workers_heard": workers, "note": note, "draining": draining}


def unknown() -> dict:
    """Лицензионный сервер не ответил: занятость НЕИЗВЕСТНА, а не ноль.

    Ноль на этом месте читается как «свободно всё» — то есть как ответ, — и
    именно из такого «ответа» человек делает вывод, что контейнеров у него нет.
    Молчание обязано выглядеть молчанием.
    """
    return {"known": False, "occupied": None, "slot_count": None, "rows": [],
            "generations_24h": None, "epochs_unacked": None,
            "contention": None, "processes_per_instance": None,
            "pending_installations": None, "pending_note": ""}


def describe(payload: dict, now: float) -> dict:
    """Ответ `/admin/instances` → то, что рисуют оба экрана.

    `occupied` приходит с сервера числом. Витрина и лицензионный сервер едут
    ОДНИМ платформенным релизом, поэтому расхождения версий между ними не
    бывает и запасного счёта здесь нет: поле, которого нет, — это сломанный
    ответ, и показать по нему число значило бы угадать. Поэтому его отсутствие
    доезжает как `None` — «сервер не назвал», — а не как ноль, который читается
    как «свободно».
    """
    listed = payload.get("slots", [])
    if not isinstance(listed, list):
        listed = []
    rows = [_slot(raw, now) for raw in listed if isinstance(raw, dict)]
    return {
        "known": True,
        "occupied": _number(payload, "occupied"),
        "slot_count": _number(payload, "slot_count"),
        "rows": rows,
        # ЗАПУСКОВ ЗА СУТКИ — ЧИСЛО, КОТОРОЕ НИЧЕГО НЕ ЗАПРЕЩАЕТ. Оно стоит на
        # экране потому, что клиент, у которого контейнеры падают, обязан
        # увидеть это раньше, чем мы прочтём его письмо; ограничителем оно не
        # является ни на одном пути — им был бюджет перевыдач, и он удалён
        # вместе с отказами, которые на него ссылались.
        "generations_24h": _number(payload, "generations_24h"),
        "epochs_unacked": _number(payload, "epochs_unacked_24h"),
        "contention": _number(payload, "slot_contention_24h"),
        "processes_per_instance": _number(payload, "processes_per_instance"),
        # УСТАНОВКИ ПРОШЛОГО РЕЛИЗА, ЕЩЁ НЕ ЗАНЯВШИЕ СЛОТ. Без этого числа
        # «занято 0 из 4» сразу после платформенного релиза читается как ОТВЕТ
        # «у вас ничего не работает» — та же ошибка, что и «занято 4 из 4» с
        # призраками, только в другую сторону. Выпущенный движок слот берёт на
        # ближайшей аренде (до восьми часов), и это ровно то, что здесь сказано.
        "pending_installations": _number(payload, "pending_installations"),
        "pending_note": _pending_note(_number(payload, "pending_installations")),
    }


def _pending_note(pending: int | None) -> str:
    """Строка про установки прошлого релиза — или пусто, когда их нет.

    Собирается ЗДЕСЬ, а не в шаблоне, по тому же правилу, что `pill` и `note`:
    кабинет и консоль не имеют права разойтись в словах об одном и том же
    числе. `None` — «сервер не назвал», и об этом молчат: догадка тут хуже
    молчания.
    """
    if not pending:
        return ""
    return (f"ещё {pending} контейнер(ов) прошлого релиза держат аренду и "
            f"займут слоты на ближайшем продлении — до 8 часов")
