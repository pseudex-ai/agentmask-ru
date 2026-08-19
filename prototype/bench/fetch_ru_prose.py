"""Обычная русская проза с Википедии — корпус для замера ПЕРЕмаскирования.

ЗАЧЕМ. Наши наборы не содержат обычного делового текста, поэтому они
сообщали 100% точности, пока «Счёт 1234 от 15.05.2025» маскировался. Нужен
объём чужого текста, в котором персональных данных заведомо нет там, где мы
их не ждём, — и любая маска на нём есть кандидат в ложное срабатывание.

НЕ КОММИТИТСЯ И НЕ ТЮНИТСЯ. Файл под .gitignore; статьи берутся по случайной
выборке, так что набор у каждого прогона свой. Подгонять детектор под него
нельзя по той же причине, по какой нельзя под make_stress.py.

Википедия отдаёт 403 без User-Agent — это не защита от ботов, а требование
их политики, и подставлять чужой заголовок не нужно: свой честный подходит.

    python3 bench/fetch_ru_prose.py --out ~/.cache/pseudex-bench/ru_prose.jsonl --count 400
"""

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://ru.wikipedia.org/w/api.php"
AGENT = "pseudex-bench/1.0 (PII over-masking evaluation; contact: local)"


def _get(params: dict[str, str]) -> dict:
    """Запрос с отступом по 429 — Википедия лимитирует анонимных клиентов.

    Отступ обязателен, а не «на всякий случай»: без него сборка падает на
    первой же сотне запросов, и тогда прибор для замера точности сам
    становится источником отказа.
    """
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    last: Exception | None = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            last = error
            if error.code not in (429, 503):
                raise
            delay = 2 ** attempt
            print(f"  {error.code} от Википедии, ждём {delay}с "
                  f"(попытка {attempt + 1}/5)", flush=True)
            time.sleep(delay)
    raise RuntimeError(f"Википедия не ответила после 5 попыток: {last}") from last


def titles(count: int) -> list[str]:
    out: list[str] = []
    while len(out) < count:
        payload = _get({"action": "query", "list": "random",
                        "rnnamespace": "0", "rnlimit": "50"})
        out.extend(item["title"] for item in payload["query"]["random"])
        time.sleep(1.0)
    return out[:count]


def extract(title: str) -> str:
    payload = _get({"action": "query", "prop": "extracts", "explaintext": "1",
                    "exsectionformat": "plain", "titles": title})
    pages = payload["query"]["pages"]
    return next(iter(pages.values())).get("extract") or ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--count", type=int, default=400)
    parser.add_argument("--min-chars", type=int, default=400)
    args = parser.parse_args()

    path = Path(args.out).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with path.open("w", encoding="utf-8") as handle:
        for title in titles(args.count * 2):
            if written >= args.count:
                break
            text = extract(title)
            if len(text) < args.min_chars:
                continue
            # Абзацами, а не статьёй целиком: детекция меряется на кусках
            # размера реального сообщения, иначе один длинный документ
            # усредняет ошибку до незаметности.
            for para in text.split("\n"):
                para = para.strip()
                if len(para) < args.min_chars:
                    continue
                handle.write(json.dumps({"title": title, "text": para},
                                        ensure_ascii=False) + "\n")
            written += 1
            time.sleep(0.6)
    print(f"{path}: {written} статей")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
