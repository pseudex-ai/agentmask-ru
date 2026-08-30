"""Расшифровки настоящих русских телефонных звонков — материал для голосового
регистра, которого у нас нет ни в одном наборе.

ЗАЧЕМ. Наш собственный корпус объявляет регистр «voice», и в нём написано, что
«современный ASR нормализует цифры». Это неправда: в 500 расшифровках Golos ноль
цифр и 21% чисел прописью. Из-за этого допущения семь дословных адресов из
реальных звонков не находились вовсе, а прибор показывал регистр покрытым.

Здесь берутся ЧУЖИЕ расшифровки, сделанные человеком, а не сгенерированные нами.
Это единственный способ узнать, как выглядит адрес, произнесённый вслух, а не
как мы думаем, что он выглядит.

ЛИЦЕНЗИЯ. OpenSTT — CC BY-NC 4.0: мерить можно, отгружать нельзя. Поэтому файл
кладётся в ~/.cache/pseudex-bench, как NEREL и остальные, и никогда в репозиторий.
SOVA RuDevices — CC BY 4.0, ограничений на использование нет.

    python3 bench/fetch_ru_speech.py            # оба набора
    python3 bench/fetch_ru_speech.py --only calls
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CACHE = Path.home() / ".cache" / "pseudex-bench"
SETS = {
    "calls": ("Joarnixon/open-stt-calls", "default", "train", "sentence",
              "OpenSTT asr_calls_2_val · CC BY-NC 4.0 · НЕ ОТГРУЖАТЬ"),
    "rudevices": ("bond005/sova_rudevices", "default", "train", "transcription",
                  "SOVA RuDevices · CC BY 4.0"),
}
BATCH = 100


def _fetch(dataset: str, config: str, split: str, offset: int) -> dict:
    url = ("https://datasets-server.huggingface.co/rows"
           f"?dataset={urllib.parse.quote(dataset, safe='')}"
           f"&config={config}&split={split}&offset={offset}&length={BATCH}")
    for attempt in range(6):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == 5:
                raise
            # Отступ, а не молчаливый пропуск: половина скачанного набора хуже
            # отсутствующего, потому что она выглядит как целый.
            # 429 приходит быстро и надолго: отступ секундами, а не мгновениями.
            time.sleep(min(60, 5 * 2 ** attempt))
            print(f"  повтор {attempt + 1} на смещении {offset}: {error}",
                  file=sys.stderr)
    raise RuntimeError("недостижимо")


def pull(key: str) -> Path:
    dataset, config, split, field, licence = SETS[key]
    out = CACHE / f"speech_{key}.jsonl"
    if out.exists() and out.stat().st_size > 1000:
        print(f"{key}: уже скачан, {sum(1 for _ in out.open()):,} строк")
        return out
    CACHE.mkdir(parents=True, exist_ok=True)
    first = _fetch(dataset, config, split, 0)
    total = first["num_rows_total"]
    print(f"{key}: {total:,} строк, {licence}")
    tmp = out.with_suffix(".tmp")
    written = 0
    with tmp.open("w", encoding="utf-8") as handle:
        for offset in range(0, total, BATCH):
            payload = first if offset == 0 else _fetch(dataset, config, split, offset)
            time.sleep(0.4)      # хост отвечает 429 на плотную серию
            for row in payload["rows"]:
                text = (row["row"].get(field) or "").strip()
                if text:
                    handle.write(json.dumps({"text": text}, ensure_ascii=False) + "\n")
                    written += 1
            if offset % 2000 == 0:
                print(f"  {offset:,}/{total:,}", flush=True)
    tmp.replace(out)
    print(f"{key}: записано {written:,} -> {out}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=sorted(SETS))
    args = parser.parse_args()
    for key in ([args.only] if args.only else sorted(SETS)):
        pull(key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
