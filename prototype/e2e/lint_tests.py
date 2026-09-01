"""Механические гейты против проверок, которые не могут провалиться.

    cd prototype && python3 e2e/lint_tests.py

Оба класса дефектов прожили в этом дереве и оба стоили нам находки:

  * `except Exception`, ГЛОТАЮЩИЙ провал. В `test_billing_e2e.py` он ловил
    ровно тот 403, из-за которого оплативший клиент не получал обслуживания, и
    молча пропускал три проверки — прогон оставался зелёным. Комментарий рядом
    называл настоящую причину («сервера может не быть»), но код приравнивал
    «сервера нет» к «сервер отказал».
  * НЕДОСТИЖИМЫЙ КОД и ДУБЛИ МЕТОДОВ. В `licensing/store.py` метод, объявленный
    `-> None`, кончался `return breaks`, за которым лежали девять строк с
    несуществующими именами; `release_instance` был определён дважды, и
    побеждало то определение, которое писало мимо блокировки.

Тавтологии (`or True`) ловятся грепом в самом workflow — здесь то, для чего
нужен разбор синтаксиса.
"""

import ast
import pathlib
import sys

_DEFAULT_ROOTS = ("licensing", "pseudex", "e2e", ".")


def _records_failure(handler: ast.ExceptHandler) -> bool:
    """Ловит ли обработчик провал, или отменяет проверку."""
    for node in ast.walk(handler):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", "") or getattr(node.func, "attr", "")
            if name in ("check", "append", "fail"):
                return True
        if isinstance(node, ast.Raise):
            return True
    return False


def swallowed_failures(path: pathlib.Path, tree: ast.AST) -> list[str]:
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        caught = node.type
        broad = (caught is None
                 or (isinstance(caught, ast.Name) and caught.id == "Exception"))
        if broad and not _records_failure(node):
            found.append(f"{path}:{node.lineno}: `except` глотает провал, "
                         f"не записывая его")
    return found


def unreachable_and_duplicates(path: pathlib.Path, tree: ast.AST) -> list[str]:
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            seen: dict[str, int] = {}
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name in seen:
                        found.append(
                            f"{path}:{item.lineno}: метод {item.name!r} объявлен "
                            f"второй раз, первый на строке {seen[item.name]} — "
                            f"побеждает последний, и это молча")
                    seen[item.name] = item.lineno
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        for index, statement in enumerate(body[:-1]):
            if isinstance(statement, (ast.Return, ast.Raise, ast.Continue, ast.Break)):
                found.append(f"{path}:{body[index + 1].lineno}: код после "
                             f"{type(statement).__name__.lower()} недостижим")
                break
            # И ТОТ ЖЕ ДЕФЕКТ ЧЕРЕЗ `with`. Настоящий обломок в `store.py`
            # выглядел именно так: `return` был последней строкой внутри
            # `with self._lock:`, а девять мёртвых строк лежали ПОСЛЕ блока, в
            # теле функции. Плоская проверка их не видит.
            if (isinstance(statement, (ast.With, ast.AsyncWith))
                    and statement.body
                    and isinstance(statement.body[-1], (ast.Return, ast.Raise))):
                found.append(f"{path}:{body[index + 1].lineno}: код после `with`, "
                             f"который всегда выходит, недостижим")
                break
    return found


def main() -> int:
    problems: list[str] = []
    roots = sys.argv[1:] or list(_DEFAULT_ROOTS)
    for root in roots:
        for path in sorted(pathlib.Path(root).glob("*.py")):
            if ".venv" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            if path.name.startswith("test_"):
                problems += swallowed_failures(path, tree)
            problems += unreachable_and_duplicates(path, tree)
    for problem in problems:
        print(problem)
    print(f"\nпроблем: {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
