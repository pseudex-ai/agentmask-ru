"""Одна дверь пакета: все команды перечислены, ни одна не тянет движок зря.

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.test_cli

ЧТО ЗДЕСЬ ПРОВЕРЯЕТСЯ И ПОЧЕМУ ИМЕННО ЭТО. Команда, которой нет в списке, — это
команда, которой нет: `compare` и `microscope` появились в один день и до этой
двери не были названы нигде, кроме собственных docstring. Поэтому список команд
сверяется с КАТАЛОГОМ: каждый модуль пакета, у которого есть `main`, либо
команда, либо назван в закрытом списке исключений с причиной.

И вторая половина — цена входа. Половина команд обязана работать на файлах
прогона без движка, без сети и без ключей (ТЗ §8); дверь, которая импортирует
всё наверху, поставила бы `natasha` и `pymorphy3` на путь `runs list` и на
`--help`. Проверяется по `sys.modules` после диспетчеризации, а не по чтению
исходника.
"""
import ast
import contextlib
import io
import json
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from bench.agentpii5 import __main__ as door
from bench.agentpii5 import contracts

HERE: Path = Path(__file__).resolve().parent
# Модули с `main`, которые командами НЕ являются, и почему. Список закрытый:
# новый модуль с `main` обязан либо попасть в дверь, либо быть назван здесь.
NOT_COMMANDS: dict[str, str] = {
    "fixtures": "`main` — это его собственный тест (test_fixtures)",
    "judge": "`main` — это его собственный тест (test_judge)",
    "metrics": "`main` — это его собственный тест (test_metrics)",
    "observe": "`main` — это его собственный тест (test_observe)",
    "perfect": "проба идеального шлюза: приёмка, гоняется как test_perfect",
    "revise": "шаг сборки корпуса; дверь к нему — команда build",
    "reportjson": "печатается командой report (--public); отдельной командой была бы "
                  "вторая дверь к одному отчёту",
    "frozen_oracle": "замороженный эталон скоринга: приёмка, гоняется как test_frozen_oracle",
}


def _dispatch(argv: list[str]) -> tuple[int, str]:
    """Дверь с подменённым `sys.argv` — и весь её вывод строкой."""
    saved = sys.argv
    out, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = door.dispatch(argv)
    finally:
        sys.argv = saved
    return code, out.getvalue() + err.getvalue()


def test_every_module_with_a_main_is_named() -> list[str]:
    """Каталог против списка команд, в обе стороны."""
    problems: list[str] = []
    modules = {path.stem for path in sorted(HERE.glob("*.py"))
               if not path.stem.startswith("test_")
               and "\ndef main(" in path.read_text(encoding="utf-8")}
    commanded = {one.module.rsplit(".", 1)[1] for one in door.COMMANDS}
    for name in sorted(modules - commanded - set(NOT_COMMANDS)):
        problems.append(f"модуль {name} запускается, но в двери его нет и причина не названа")
    for name in sorted(set(NOT_COMMANDS) - modules):
        problems.append(f"в списке исключений {name}, а такого запускаемого модуля нет")
    for name in sorted(commanded & set(NOT_COMMANDS)):
        problems.append(f"{name} и команда, и исключение — одно из двух неправда")
    return problems


def test_one_name_per_thing() -> list[str]:
    """Интеграторская проверка: у вещи, которую называют несколько модулей, одно
    имя и одно место.

    Все три дефекта тут были: `BENCHMARK = "agentpii5"` жил в двух модулях,
    путь до реестра считали трое (один — импортом из `trend`, модуля, который к
    файлу отношения не имеет), и один `main` принимал `argv`, когда остальные
    двенадцать читают `sys.argv`. Ни один из трёх не ломает ничего сегодня —
    они ломают то, что поедет следом: переименованный файл, найденный в двух
    местах из трёх, и команда, которую дверь не может позвать единообразно.
    """
    problems: list[str] = []
    for path in sorted(HERE.glob("*.py")):
        if path.stem.startswith("test_"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            named = (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                     and node.target.id == "BENCHMARK")
            if named and path.stem != "contracts":
                problems.append(f"{path.name}: второе имя бенчмарка — оно едет в реестр "
                                f"и в report.json, и тренд сложил бы два бенчмарка в один")
            if (isinstance(node, ast.Constant) and node.value == "runs.json"
                    and path.stem != "runinfo"):
                problems.append(f"{path.name}: путь до реестра считается второй раз")
            if (isinstance(node, ast.FunctionDef) and node.name == "main"
                    and node.col_offset == 0 and node.args.args):
                problems.append(f"{path.name}: main принимает аргументы, а дверь зовёт "
                                f"двенадцать команд одинаково")
    return problems


def test_help_lists_every_command() -> list[str]:
    """`--help` печатает каждую команду с одной строкой о ней, и выходит нулём;
    вызов без аргументов печатает то же и выходит двойкой — ничего не сделано."""
    problems: list[str] = []
    code, printed = _dispatch(["--help"])
    if code != 0:
        problems.append(f"--help вышел {code}")
    for one in door.COMMANDS:
        if one.name not in printed:
            problems.append(f"--help не называет команду {one.name}")
        elif one.summary.split(":")[0][:24] not in printed:
            problems.append(f"команда {one.name} названа без строки о том, зачем она")
    empty_code, empty = _dispatch([])
    if empty_code != 2:
        problems.append(f"вызов без команды вышел {empty_code}, а ничего не сделано")
    if empty.splitlines() != printed.splitlines():
        problems.append("пустой вызов и --help печатают разные списки")
    code, printed = _dispatch(["nonsense"])
    if code != 2:
        problems.append(f"неизвестная команда вышла {code}")
    if not all(one.name in printed for one in door.COMMANDS):
        problems.append(f"отказ не называет весь список: {printed!r}")
    return problems


def test_an_offline_command_does_not_load_the_engine() -> list[str]:
    """ТЗ §8: команды по файлам прогона работают без движка. Дверь ленива, и
    это проверяется после ВЫЗОВА, а не чтением импортов."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        registry = Path(tmp) / "runs.json"
        registry.write_text(json.dumps({"version": 1, "runs": []}), encoding="utf-8")
        code, printed = _dispatch(["runs", "list", "--runs", str(registry)])
        if code != 0:
            problems.append(f"`runs list` по пустому реестру вышел {code}: {printed!r}")
    _dispatch(["--help"])
    loaded = sorted(name for name in sys.modules
                    if name.split(".")[0] == contracts.FORBIDDEN_IMPORT_PREFIX)
    if loaded:
        problems.append(f"дверь притащила движок: {loaded}")
    if "bench.agentpii5.harness" in sys.modules:
        problems.append("дверь импортировала harness, хотя звали offline-команду")
    return problems


def test_the_door_reaches_the_command_with_its_arguments() -> list[str]:
    """Остаток строки доезжает до команды как есть, и `--help` команды называет
    ту дверь, которой человек воспользовался, — иначе он скопирует из подсказки
    строку, которой не набирал."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        registry = Path(tmp) / "runs.json"
        registry.write_text(json.dumps({"version": 1, "runs": []}), encoding="utf-8")
        code, printed = _dispatch(["runs", "show", "нет-такого", "--runs", str(registry)])
        if code != 2 or "нет-такого" not in printed:
            problems.append(f"аргументы не доехали до команды: {code} {printed!r}")
    saved = sys.argv
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            door.dispatch(["compare", "--help"])
        problems.append("`compare --help` не завершил процесс, как делает argparse")
    except SystemExit as exited:
        if exited.code != 0:
            problems.append(f"`compare --help` вышел {exited.code}")
    finally:
        sys.argv = saved
    if "python3 -m bench.agentpii5 compare" not in out.getvalue():
        problems.append(f"подсказка команды называет не ту дверь: {out.getvalue()[:120]!r}")
    return problems


def test_report_public_goes_to_the_public_writer() -> list[str]:
    """§5.3: `report --public` печатает публичную подстроку. Она живёт в другом
    модуле (`reportjson` импортирует `report`, обратный импорт был бы циклом), и
    дверь — то единственное место, где флаг решает, кого звать. Проверяется по
    ВЫВОДУ: приватные поля отсутствуют, публичные на месте."""
    from bench.agentpii5.test_report import RUN_ID, build_run

    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        v5_dir = build_run(root, RUN_ID, True)
        v4_dir = build_run(root, "baseline01", False)
        code, printed = _dispatch(["report", "--public", str(v5_dir), str(v4_dir)])
        if code != 0:
            problems.append(f"`report --public` вышел {code}: {printed[:200]!r}")
            return problems
        body = printed[printed.index("{"):printed.rindex("}") + 1]
        document = json.loads(body)
        for key in ("cost", "judge", "run_id", "run_dir", "models"):
            if key in document:
                problems.append(f"приватное поле {key} уехало в публичный вывод")
        for key in ("lines", "corpus_digest", "incomplete"):
            if key not in document:
                problems.append(f"публичный вывод без {key}")
        code, printed = _dispatch(["report", str(v5_dir), str(v4_dir)])
        if code != 0 or "AgentPII-RU v5" not in printed:
            problems.append(f"`report` без флага перестал печатать текстовый отчёт: {code}")
    return problems


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("every_module_with_a_main_is_named", test_every_module_with_a_main_is_named),
        ("one_name_per_thing", test_one_name_per_thing),
        ("help_lists_every_command", test_help_lists_every_command),
        ("an_offline_command_does_not_load_the_engine",
         test_an_offline_command_does_not_load_the_engine),
        ("the_door_reaches_the_command_with_its_arguments",
         test_the_door_reaches_the_command_with_its_arguments),
        ("report_public_goes_to_the_public_writer", test_report_public_goes_to_the_public_writer),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("cli: PASS" if not failures else "cli: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
