"""Полный замер: все бенчмарки одним прогоном, все выводы на диск.

ЗАЧЕМ ОТДЕЛЬНЫЙ ФАЙЛ, А НЕ СПИСОК КОМАНД В ГОЛОВЕ. Числа этого продукта живут
в коммит-сообщениях и в CLAUDE.md, и каждое из них когда-то было получено
командой, которую никто не записал. Сравнить два замера можно только если
известно, ЧТО именно гонялось, на каком коде и на каких данных — поэтому здесь
рядом с выводом каждого шага пишется манифест: git-версия, время, код возврата,
длительность и sha256 входных корпусов.

ПРОПУСК ЗАПИСЫВАЕТСЯ, А НЕ ЗАМАЛЧИВАЕТСЯ. Половина эвалов требует корпусов,
которых на машине может не быть (NEREL, pii-bench, речь, диалоги продакшна).
Прогон, тихо пропустивший недостающее, отчитывается по тому, что нашлось, — а
нашлось обычно самое лёгкое. Каждый пропуск попадает в манифест с причиной.

    python3 bench/run_all.py                    # всё, что есть данные прогнать
    python3 bench/run_all.py --only golden,dirty
    python3 bench/run_all.py --out bench/runs/2026-09-01
"""
import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = pathlib.Path.home() / ".cache" / "pseudex-bench"
NEREL = CACHE / "nerel" / "NEREL-v1.1"


def _sha(path: pathlib.Path) -> str:
    if not path.exists():
        return ""
    if path.is_dir():
        return "dir"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


# (имя, аргументы, что должно существовать, зачем этот шаг)
def steps() -> list[tuple[str, list[str], list[pathlib.Path], str]]:
    return [
        # --- наборы порождаются заново: они в gitignore и обязаны быть свежими
        ("00-make-golden", ["make_dataset.py"], [], "порождает dataset.json"),
        ("00-make-dirty", ["make_dirty.py"], [], "порождает dirty.json"),
        ("00-make-stress", ["make_stress.py"], [], "порождает stress.json"),
        ("00-make-holdout", ["make_holdout.py"], [], "порождает holdout.json"),
        ("00-make-addr-fresh", ["make_addr_real.py", "addr_s41.json", "41"], [],
         "адресный набор на СВЕЖЕМ зерне — по нему не настраивались"),

        # --- наши наборы
        ("10-golden", ["eval_detect.py"], [ROOT / "dataset.json"],
         "золотой набор: полнота и точность по типам"),
        ("11-dirty", ["eval_dirty.py"], [ROOT / "dirty.json"],
         "грязный набор: F2, ложные маски, тип-слепая утечка"),
        ("12-stress", ["eval_stress.py"], [ROOT / "stress.json"],
         "состязательный набор, построен ЛОМАТЬ детектор"),
        ("13-addr-fresh-seed", ["eval_dirty.py", "addr_s41.json"],
         [ROOT / "addr_s41.json"], "адреса на зерне, которого движок не видел"),
        ("14-overmasking", ["test_overmasking.py"], [],
         "чистая деловая речь: сколько лишнего маскируем, с интервалом"),

        # --- чужие корпуса, чужая разметка
        ("20-nerel-recall", ["bench/eval_external_ner.py", str(NEREL),
                             "--splits", "dev,test"], [NEREL],
         "полнота на корпусе, который писали не мы"),
        ("21-nerel-precision", ["bench/eval_external_precision.py", str(NEREL)], [NEREL],
         "что мы маскируем из того, чего аннотатор не размечал"),
        ("22-massive-ru", ["bench/eval_massive_ru.py"],
         [CACHE / "massive_ru_test.parquet"],
         "16 521 реплика, слоты размечены третьей стороной, ноль заглавных"),
        ("23-pii-bench", ["bench/eval_piibench.py"],
         [CACHE / "pii-bench" / "data" / "domain-00000-of-00001.parquet"],
         "чужой русский корпус ПД в чатовом регистре"),
        ("24-voice", ["bench/voice/score.py"], [CACHE / "voice_addresses.json"],
         "настоящие звонки: адреса, произнесённые вслух"),
        ("25-gate", ["bench/gate/sheet.py"], [ROOT / "bench" / "gate" / "labels.json"],
         "600 вхождений живой речи, размеченных РУКОЙ: потолок словарного гейта"),
        # NEREL-проза, а не Википедия: `fetch_ru_prose.py` ходит в Википедию и
        # сегодня получает 429, а этот файл — те же чужие тексты, уже на диске.
        ("26-prose-volume", ["bench/eval_overmasking_volume.py",
                             str(CACHE / "nerel_prose.jsonl")],
         [CACHE / "nerel_prose.jsonl"],
         "новостная проза объёмом: над-маскирование там, где ПД нет вовсе"),

        # --- где и как ломается
        ("30-noise-ladder", ["bench/eval_noise_ladder.py", "--dataset", "dataset.json"],
         [ROOT / "dataset.json"], "ступени шума живого чата: где детекция падает"),
        ("31-noise-by-type", ["bench/eval_noise_by_type.py", "dataset.json"],
         [ROOT / "dataset.json"], "та же лестница ПО ТИПАМ — одно число прячет виновника"),
        ("32-metamorphic", ["bench/eval_metamorphic.py"],
         [ROOT / "bench" / "agentpii" / "corpus.json"],
         "инвариантность к переписыванию входа"),
        ("33-gar-cut", ["bench/eval_gar_cut.py"],
         [ROOT / "licensing" / "data" / "gar_streets.tsv"],
         "чем платится отсечение словаря улиц по частоте"),
        ("34-fuzz-registers", ["bench/fuzz_registers.py"], [],
         "одни и те же значения × стили письма"),

        # --- AgentPII-RU v3, три оси
        ("40-v3-offline", ["bench/agentpii3/score.py", "bench/agentpii3/corpus.json"],
         [ROOT / "bench" / "agentpii3" / "corpus.json"],
         "три оси на всём корпусе, детерминированный судья"),

        # --- AgentPII-RU v4, три плеча (без модели)
        ("41-v4-build", ["bench/agentpii4/build.py", "--check"],
         [ROOT / "bench" / "agentpii4" / "corpus.json"],
         "корпус v4: валидатор, prove_no_search, покрытие"),
        ("42-v4-smoke", ["bench/agentpii4/smoke.py"], [],
         "уровень A: каждый класс таксономии производим на фейковом шлюзе"),
        ("43-v4-scripted-engine", ["bench/agentpii4/smoke.py", "--engine"],
         [ROOT / "bench" / "agentpii4" / "corpus.json"],
         "скриптовый агент через НАСТОЯЩИЙ шлюз: труба, не модель"),

        # --- продуктовые проверки
        ("50-loop", ["test_loop.py"], [], "ПД не доходят до модели, вызов инструмента жив"),
        ("51-product", ["test_product.py"], [], "тенантность, аудит, потоковая детокенизация"),
        ("52-vault", ["vault_test.py"], [], "канонизация и переживание перезапуска"),
        ("53-persona", ["test_persona_defects.py"], [], "дефекты, найденные прогоном персон"),
        ("54-collisions", ["test_collisions.py"], [],
         "подмена, совпавшая с настоящим значением: обе половины"),
        ("55-hard-cases", ["test_hard_cases.py"], [],
         "неудобное, редкое и намеренно враждебное: детекция, возврат, без лишнего"),
        ("56-prose-fragments", ["test_prose_fragments.py"], [],
         "кусок и производная подмены в ответе клиенту возвращаются настоящим значением"),
        # ЧЕТЫРЕ НАБОРА, КОТОРЫХ ЗДЕСЬ НЕ БЫЛО, И ДВА ИЗ НИХ БЫЛИ КРАСНЫМИ.
        # `test_argument_form` и `test_coverage_152fz` держали ожидания,
        # устаревшие после правок 31.08 и 07.09, и никто этого не видел: батарея
        # гоняла восемь движковых наборов из семнадцати, а «зелёная батарея» в
        # каждом отчёте читалась как «всё зелёное». Набор, который не запускают,
        # не отличим от отсутствующего.
        ("58-argument-form", ["test_argument_form.py"], [],
         "форма аргумента: порядок частей, набор частей, регистр"),
        ("59-names-morphology", ["test_names_morphology.py"], [],
         "морфология имён: падеж, род, подмена в косвенном слоте"),
        ("60-coverage-152fz", ["test_coverage_152fz.py"], [],
         "все типы ПД, названные 152-ФЗ, ловятся и типизируются верно"),
        ("61-credentials", ["test_credentials.py"], [],
         "секреты по опубликованным префиксам, а не по энтропии"),
        ("57-derived-forms", ["test_derived_forms.py"], [],
         "транслит и инициалы в аргументе: конвенция модели, разговор решает неоднозначность"),
        # НЕ ПРО ДВИЖОК, А ПРО САМИ ПРОВЕРКИ, и поэтому стоит здесь, а не в
        # гейтах: гейтам нужен Docker, а этот шаг читает их исходник и не
        # запускает ничего. Дешёвый, детерминированный, и краснеет ровно тогда,
        # когда кто-то ослабляет гейт до утверждения, проходящего на пустоте.
        ("62-gate-audit", ["e2e/audit_gates.py", "--quiet"], [],
         "ни один гейт не выносит вердикт над пустым свидетельством"),
        # Единственный путь, которым лицензионный сервер пойдёт в проде: подъём
        # на томе, который уже жил. Всё остальное про него гоняется на чистой
        # базе, поэтому «no such column: pubkey» на апгрейде не видел никто.
        ("63-license-upgrade", ["-m", "licensing.test_store_upgrade"], [],
         "лицензионный сервер поднимается на томе прошлой версии"),
        # Обещание живёт в русской прозе витрины, механизм — здесь. Оба
        # известных расхождения нашлись глазами, а не проверкой.
        ("64-published-claims", ["test_published_claims.py"], [],
         "числа на лендинге совпадают с числами, по которым работает движок"),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="")
    parser.add_argument("--only", default="", help="запятые: имена шагов")
    args = parser.parse_args()

    stamp = time.strftime("%Y-%m-%d")
    out = pathlib.Path(args.out) if args.out else ROOT / "bench" / "runs" / stamp
    out.mkdir(parents=True, exist_ok=True)

    wanted = {name.strip() for name in args.only.split(",") if name.strip()}
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                           capture_output=True, text=True).stdout.strip()

    records: list[dict[str, object]] = []
    for name, argv, needs, why in steps():
        if wanted and not any(name.startswith(w) or w in name for w in wanted):
            continue
        missing = [str(path) for path in needs if not path.exists()
                   or (path.is_file() and path.stat().st_size == 0)]
        if missing:
            records.append({"step": name, "why": why, "status": "SKIP",
                            "missing": missing})
            print(f"SKIP  {name}: нет данных — {missing[0]}")
            continue
        started = time.time()
        proc = subprocess.run([sys.executable] + argv, cwd=ROOT, env=env,
                              capture_output=True, text=True)
        took = time.time() - started
        (out / f"{name}.txt").write_text(
            f"$ python3 {' '.join(argv)}\n\n{proc.stdout}\n{proc.stderr}",
            encoding="utf-8")
        records.append({"step": name, "why": why, "status":
                        "OK" if proc.returncode == 0 else "FAIL",
                        "rc": proc.returncode, "seconds": round(took, 1),
                        "argv": argv})
        print(f"{'OK  ' if proc.returncode == 0 else 'FAIL'}  {name}  {took:.0f} с")

    manifest = {
        "date": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "git_head": head,
        "git_dirty": bool(dirty),
        "python": sys.version.split()[0],
        "inputs": {
            "nerel": _sha(NEREL),
            "massive_test": _sha(CACHE / "massive_ru_test.parquet"),
            "pii_bench": _sha(CACHE / "pii-bench" / "data" / "domain-00000-of-00001.parquet"),
            "voice_addresses": _sha(CACHE / "voice_addresses.json"),
            "rudevices_addresses": _sha(CACHE / "rudevices_addresses.json"),
            "gate_labels": _sha(ROOT / "bench" / "gate" / "labels.json"),
            "agentpii3_corpus": _sha(ROOT / "bench" / "agentpii3" / "corpus.json"),
            "agentpii4_corpus": _sha(ROOT / "bench" / "agentpii4" / "corpus.json"),
            "nerel_prose": _sha(CACHE / "nerel_prose.jsonl"),
        },
        "steps": records,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    failed = [r["step"] for r in records if r["status"] == "FAIL"]
    skipped = [r["step"] for r in records if r["status"] == "SKIP"]
    print(f"\nготово -> {out}")
    print(f"  прошло {sum(1 for r in records if r['status'] == 'OK')}, "
          f"упало {len(failed)}, пропущено {len(skipped)}")
    if failed:
        print(f"  УПАЛО: {failed}")
    if skipped:
        print(f"  пропущено (нет данных): {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
