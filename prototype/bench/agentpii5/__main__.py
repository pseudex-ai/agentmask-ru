"""AgentPII-RU v5 — ОДНА ДВЕРЬ ко всем командам приватного бенчмарка.

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5 --help          # список команд, по строке на каждую
    python3 -m bench.agentpii5 <команда> --help  # аргументы одной команды

ЗАЧЕМ ДВЕРЬ, КОГДА КАЖДЫЙ МОДУЛЬ И ТАК ЗАПУСКАЕТСЯ. Двенадцать команд лежали
двенадцатью модулями, и узнать их можно было только чтением каталога: `compare`
и `microscope` появились в один день и не попали никуда, кроме собственных
docstring. Список команд — это то, что человек читает через месяц, и он обязан
быть в одном месте, вместе с одной строкой о том, зачем каждая.

МОДУЛИ ИМПОРТИРУЮТСЯ ЛЕНИВО, и это не оптимизация. `harness` тянет движок
(natasha, pymorphy3, SQLCipher) — секунды и весь стек модели; `compare`,
`microscope`, `trend`, `repro`, `runs` и `quarantine` обязаны работать на файлах
прогона БЕЗ движка, без сети и без ключей (ТЗ §8). Дверь, импортирующая всё
наверху, поставила бы движок на путь каждой из них — и `--help` грузил бы его
тоже.

АРГУМЕНТЫ НЕ РАЗБИРАЮТСЯ ЗДЕСЬ. Дверь выбирает команду и отдаёт ей ОСТАТОК
строки через `sys.argv`; каждая команда остаётся владельцем своих флагов. Второй
разбор — это второе место, где `--tier` может значить не то, и оно расходится с
первым на первой же правке.
"""
import importlib
import sys
from dataclasses import dataclass

# Команда, которая печатает публичную подстроку отчёта, живёт в другом модуле:
# `reportjson` импортирует `report`, и обратный импорт был бы циклом. Флаг
# маршрутизируется ЗДЕСЬ, а не дублируется там — публичный состав остаётся
# одним списком в одном файле (`reportjson.PUBLIC_TOP_LEVEL`).
PUBLIC_FLAG: str = "--public"


@dataclass(frozen=True)
class Command:
    """Одна команда: имя, модуль, что дописать к аргументам, и строка о том,
    зачем она. `prepend` существует ради `dry-run`: это не отдельная программа,
    а прогон, который ничего не тратит, и второй модуль под неё означал бы две
    оценки одного и того же."""

    name: str
    module: str
    prepend: tuple[str, ...]
    summary: str


COMMANDS: tuple[Command, ...] = (
    Command("run", "bench.agentpii5.harness", (),
            "живой прогон: ярус или --ids, модели, потолок, --label (тратит деньги)"),
    Command("dry-run", "bench.agentpii5.harness", ("--dry-run",),
            "оценка ДО запуска: случаи, вызовы, токены, $ и минуты — по прошлым прогонам"),
    Command("report", "bench.agentpii5.report", (),
            "отчёт по готовому каталогу; --public — только то, что можно показать наружу; "
            "--selftest — мутанты метрик"),
    Command("compare", "bench.agentpii5.compare", (),
            "любой прогон против любого: строки, разница с интервалом, --cases — по случаям"),
    Command("hop-report", "bench.agentpii5.hop_report", (),
            "offline completed cohort: historical metrics and versioned actual-hop evidence"),
    Command("live", "bench.agentpii5.live", (),
            "живые метрики ИДУЩЕГО прогона: все 13 спринта + переходы + actual/causal, "
            "<run_dir> или --latest"),
    Command("microscope", "bench.agentpii5.microscope", (),
            "один случай целиком: что видела модель, что написала, что вернулось, вердикт"),
    Command("trend", "bench.agentpii5.trend", (),
            "строка на прогон по датам и регресс между соседними — из реестра и report.json"),
    Command("repro", "bench.agentpii5.repro", (),
            "одна команда, повторяющая прогон, и честный список того, чего сегодня нет"),
    Command("runs", "bench.agentpii5.runinfo", (),
            "реестр прогонов: `runs list` — все строки, `runs show <id>` — одна"),
    Command("quarantine", "bench.agentpii5.quarantine", (),
            "случаи, нестабильные у ВСЕХ плеч в трёх прогонах подряд — дефект случая"),
    Command("calibration", "bench.agentpii5.calibration", (),
            "судья: export → разметка руками → import → штамп на прогон"),
    Command("build", "bench.agentpii5.build", (),
            "корпус и лестница: --check доказывает рендер моком, --provenance — §6.1"),
    Command("provider", "bench.agentpii5.provider", (),
            "что прогон ЗАПИШЕТ о провайдере, моделях и ценах — без единого вызова"),
)
BY_NAME: dict[str, Command] = {one.name: one for one in COMMANDS}


def usage_lines() -> list[str]:
    """Список команд — по строке на каждую, в порядке рабочего дня: сделать
    прогон, прочитать его, сравнить, разобрать один случай, прибраться."""
    width = max(len(one.name) for one in COMMANDS)
    out = [f"python3 -m bench.agentpii5 <команда> [аргументы]", ""]
    out += [f"  {one.name:{width}}  {one.summary}" for one in COMMANDS]
    out += ["",
            "«<команда> --help» печатает аргументы этой команды.",
            "Рецепты (добавить случаи · прогон · сравнить · повторить · один случай · "
            "откалибровать судью) — bench/agentpii5/README.md."]
    return out


def dispatch(argv: list[str]) -> int:
    """Выбрать команду и отдать ей остаток строки.

    Неизвестное имя — отказ СО СПИСКОМ, а не подсказка «ближайшего»: команды
    называются словами, которые человек помнит по README, и угаданная за него
    команда может оказаться той, что тратит деньги.
    """
    if not argv or argv[0] in ("-h", "--help", "help"):
        for line in usage_lines():
            print(line)
        return 0 if argv else 2
    name, rest = argv[0], argv[1:]
    command = BY_NAME.get(name)
    if command is None:
        print(f"нет команды {name!r}: есть {', '.join(one.name for one in COMMANDS)}",
              file=sys.stderr)
        return 2
    module_name = command.module
    if name == "report" and PUBLIC_FLAG in rest:
        module_name = "bench.agentpii5.reportjson"
    module = importlib.import_module(module_name)
    sys.argv = [f"python3 -m bench.agentpii5 {name}", *command.prepend, *rest]
    return int(module.main())


if __name__ == "__main__":
    raise SystemExit(dispatch(sys.argv[1:]))
