---
name: measure
description: Run the full pseudex measurement battery and read it correctly — ten suites, four external corpora, the noise ladder, over-masking volume. Use before and after ANY detection change, or when asked how good detection currently is. Includes the baseline numbers to compare against, how to get the corpora (they are gitignored and get lost), and which low numbers are instrument artifacts rather than defects.
---

# Батарея измерений

## Сначала корпуса — они не в git и теряются

Живут в `~/.cache/pseudex-bench`, а не в `/tmp`: `/tmp` чистится при
перезагрузке и дважды унёс NEREL.

```bash
git clone --depth 1 https://github.com/nerel-ds/NEREL.git ~/.cache/pseudex-bench/nerel
for f in domain entity; do
  curl -L --create-dirs -o ~/.cache/pseudex-bench/pii-bench/data/$f-00000-of-00001.parquet \
    https://huggingface.co/datasets/hivetrace/pii-bench/resolve/main/data/$f-00000-of-00001.parquet
done
```

Генерируемые наборы пересобираются перед каждым замером — они гитигнорены:

```bash
cd prototype
python3 make_dataset.py && python3 make_dirty.py
```

## Быстрый круг (минуты) — гонять всегда

```bash
cd prototype && source .venv/bin/activate
for t in test_loop test_product vault_test test_persona_defects test_overmasking \
         test_localui test_hard_cases test_names_morphology test_credentials \
         test_coverage_152fz test_perf_masking; do
  printf "%-24s" "$t"; python3 $t.py >/dev/null 2>&1 && echo PASS || echo FAIL
done
python3 eval_detect.py   # голден, 298 значений
python3 eval_dirty.py    # грязный, 150 + жёсткие негативы
```

Оба евала теперь **возвращают код**, а не только печатают: порог 100% по обеим
осям, ноль утечек, ноль ложных масок.

## Полный круг (десятки минут) — перед коммитом, меняющим детекцию

```bash
python3 bench/agentpii/score.py bench/agentpii/corpus.json
python3 bench/eval_piibench.py
python3 bench/eval_external_ner.py ~/.cache/pseudex-bench/nerel/NEREL-v1.1 --splits dev,test
python3 bench/eval_external_precision.py ~/.cache/pseudex-bench/nerel/NEREL-v1.1
python3 bench/eval_noise_ladder.py --dataset dataset.json
python3 bench/fuzz_registers.py
```

## Базовая линия на 2026-08-20

Сверяться с ней. Просадка **любого** числа — повод остановиться.

```
десять суит PASS · фаззер 132/132
голден 298 = 100%/100% · грязный 150 = 100%/100%, жёстких негативов 0/12

AgentPII-RU  полнота 98,7 · покрытие 98,0 · негативы 100 · круг 97,9 · согласованность 91,4
             круг «из них»: починен пробел 17, форма изменена 16,
                            починена латиница 12, вернулась часть 8
PII-Bench    по закону 80,0/77,8 · ADDRESS покрытие 75,6 · NAME 98,2 · PASSPORT 83,3
NEREL        PERSON 92,5 · кириллица 93,4 · защищено 92,9 · точность 99,4
лестница     0: 100 · 1 строчными: 94,0 · 2 без пункт.: 87,2 · 3 опечатка: 75,2 · 4: 74,5
задержка     2,0 мс на сообщение офлайн, кеш 5–20× на растущей стенограмме
```

## Как читать — четыре оси, и они не взаимозаменяемы

- **Полнота** — спан пересёкся с эталоном.
- **Покрытие** — спан найден **целиком**. Разница с полнотой это утёкшие хвосты:
  «Кзнецов Дмитрий», опознанный как «Дмитрий», засчитывается в полноту, пока
  фамилия уходит к модели открытым текстом. Никогда не сливать эти два числа.
- **Круг** — настоящее значение вернулось в инструмент. Единственное число,
  которое клиент чувствует напрямую.
- **Согласованность** — один человек, один псевдоним.

## Низкие числа, которые НЕ дефекты

Прежде чем чинить, прочитай:

- **PII-Bench, BANK_CARD_NUMBER 4,3%** — 88 из 92 карт корпуса **не проходят
  Луна**, их выдумал генератор. Мы находим ровно четыре валидных.
- **PII-Bench, TOKEN 18,9%** — разногласие по определению. Их TOKEN это любая
  энтропия; наши учётные данные привязаны к опубликованным префиксам, потому
  что git SHA, UUID и base64-картинка тоже высокоэнтропийны и ни один не секрет.
- **PII-Bench, CVC 0%** — своего типа нет: три цифры без карты рядом неотличимы
  от любого числа.
- **PII-Bench, OGRN 0%** — намеренно. Юрлицо не субъект данных. ОГРНИП (15 цифр)
  маскируется, ОГРН (13) нет.
- **NEREL, CITY / LOCATION / FACILITY** — голый топоним не ПД по решению.
- **Лестница, колонка «без городов»** — набор размечает «Москва» как LOC, а
  продукт её намеренно не маскирует. Считая это пропуском, прибор обвиняет за
  правило, которое работает.

Прибор печатает эти оговорки сам. Если число выглядит катастрофой — сначала
читай строку рядом с ним.

## A/B против HEAD, когда корпус изменился

Единственный честный способ доказать отсутствие регрессии, если корпус
пересобрался:

```bash
python3 /tmp/dump_spans.py <корпус.jsonl> /tmp/after.tsv
git stash push -q pseudex licensing
python3 /tmp/dump_spans.py <корпус.jsonl> /tmp/before.tsv
git stash pop -q
comm -13 <(sort /tmp/before.tsv) <(sort /tmp/after.tsv)   # что добавилось
comm -23 <(sort /tmp/before.tsv) <(sort /tmp/after.tsv)   # что пропало
```

Смотреть глазами на обе стороны. «+12 спанов» может быть починкой границ, а
может быть двенадцатью ложными масками — цифра этого не скажет.

## Перемаскирование на объёме чужого текста

```bash
python3 bench/fetch_ru_prose.py --out ~/.cache/pseudex-bench/ru_prose.jsonl --count 220
python3 bench/eval_overmasking_volume.py ~/.cache/pseudex-bench/ru_prose.jsonl
```

Википедия жёстко лимитирует анонимных: скрипт отступает по 429 и **падает**, а
не дописывает половину файла, которому прибор потом поверит.

## Правило, которое дороже всех

**Наши собственные наборы не могут сказать правду о точности.** Они показывали
100%, пока «Счёт 1234 от 15.05.2025» маскировался — не были неправы, просто не
содержали обычного делового текста. Поэтому внешних измерений четыре, и ни одно
не заменяет остальные.
