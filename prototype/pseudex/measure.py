"""Мера самого себя: что за сборка сейчас исполняется.

ЧЕГО ЭТО НЕ ДЕЛАЕТ, СКАЗАНО ПЕРВЫМ. Это НЕ защита от патча. Код, который меряет,
живёт в том же файле, который меряют, — тот, кто убрал проверку, уберёт и меру
или зашьёт правильный хеш. На чужой машине иначе не бывает, и обещать здесь
нечего.

ЧТО ЭТО ДЕЛАЕТ. Мера едет ВНУТРИ подписанного отчёта о расходе, то есть попадает
в нашу запись с датой. Патч перестаёт быть бесплатным и незаметным: его надо
найти, снять И подделать меру, и делать это заново на каждом релизе. А если
мера не пришла или не совпала с известной нам для этой версии — у нас есть
датированный факт, а не догадка. Ровно та же логика, что у разрывов цепи
отчётов: не невозможность, а доказуемость.

ЧТО ИМЕННО МЕРЯЕТСЯ. В релизе — файл собственного исполняемого образа целиком.
В сборке из исходников такого файла нет, поэтому меряется отсортированный
список хешей модулей пакета: разработчику это даёт ту же проверку «то ли
исполняется, что лежит на диске», а гейт P-серии сравнивает release-меру с
известной.
"""
import hashlib
import os
import sys

_CHUNK = 1 << 20
_cached: str | None = None


def _hash_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _compiled_binary() -> str | None:
    """Путь к собственному исполняемому файлу в скомпилированной сборке."""
    # Nuitka ставит `__compiled__` в модули; у запущенного бинарника
    # `sys.frozen`-подобного признака нет, поэтому опираемся на то, что
    # исполняемый файл — не интерпретатор.
    executable = sys.executable or ""
    if not executable or os.path.basename(executable).startswith("python"):
        return None
    return executable if os.path.isfile(executable) else None


def build_measurement() -> str:
    """`sha256:<hex>` собственного образа, или `modules:<hex>` при запуске из
    исходников. Считается один раз за процесс — файл на 70 МБ, и делать это на
    каждый отчёт незачем."""
    global _cached
    if _cached is not None:
        return _cached
    binary = _compiled_binary()
    if binary is not None:
        try:
            _cached = "sha256:" + _hash_file(binary)
            return _cached
        except OSError:
            pass
    here = os.path.dirname(os.path.abspath(__file__))
    digest = hashlib.sha256()
    for name in sorted(os.listdir(here)):
        if not name.endswith(".py"):
            continue
        try:
            with open(os.path.join(here, name), "rb") as handle:
                digest.update(name.encode("utf-8"))
                digest.update(hashlib.sha256(handle.read()).digest())
        except OSError:
            continue
    _cached = "modules:" + digest.hexdigest()
    return _cached
