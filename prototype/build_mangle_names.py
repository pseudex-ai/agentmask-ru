"""Rename PRIVATE crown symbols to opaque names BEFORE Nuitka compiles (WS-1).

Nuitka stores every def's `co_name`/qualname as a plaintext string in the constants
blob, so `strings`/nuitka-static-unpacker read the full name-skeleton of the engine —
31 crown function/class names and 85 module qualnames, measured, with ZERO native-code
reverse-engineering (research/2026-09-15). Docstrings are already stripped and beacon
strings hardened; this closes the remaining leak by renaming the symbols themselves, so
the blob carries `_z0007`, not `Vault._unique_token`. The research showed this is the
ONLY durable free defense (blob-encryption, paid or DIY, is undone by the same unpacker,
which recovers the key from the binary; renaming has no key to recover).

SAFETY — this runs against real, dynamic Python, so a wrong rename is a SILENT product
break, not a crash. The rules are deliberately conservative:
  * PRIVATE only — a leading single underscore, never dunder, never a public name (the
    API surface and anything a caller might reference by its public name stay put).
  * FUNCTIONS and CLASSES only — never a variable, argument, attribute-that-is-not-a-
    method, or a pydantic/dataclass FIELD.
  * UNIQUE — the name is defined exactly once in the whole program, so every reference to
    it (`name`, `self.name`, `obj.name`) resolves to that one def and renames consistently.
  * NOT DYNAMIC — the name appears in no string literal anywhere (rules out getattr/
    setattr/hasattr, string-dispatch tables, __all__, importlib), and is not in the
    hand-kept exclusion allowlist below.
Whole-program: every path is parsed together, so a rename updates the def, every use, and
every `from x import _name` alias across all files at once.

Usage:  python3 build_mangle_names.py ./pseudex ./serve_main.py
Verify BEFORE the Nuitka build by running the test battery against the mangled copy (see
the WS-1 flow); a broken rename shows there, cheaply, not in a 30-minute compile.
"""
import ast
import sys
from pathlib import Path

# Names that LOOK renameable by the rules but must NOT move — dynamic or contract-bound
# in a way the static rules cannot see. Keep this list short and justified.
_EXCLUDE: frozenset[str] = frozenset({
    "_lifespan",       # FastAPI lifespan, wired by framework introspection
    "_release",        # generated module pseudex/_release.py (LICENSE_PUBKEY, ENGINE_VERSION)
    "_morph_compat",   # import-time pymorphy2->3 alias, bound by name eagerly
})

# Modules whose PUBLIC API is a CROSS-PACKAGE CONTRACT: the licensing server (a separate,
# UNMANGLED image) imports these by name (`from pseudex.bundle import merge_payload`, ...).
# Their public names are wire-crypto / interfaces / the license client — the ALGORITHM,
# not the agent-transparency crown — so leaving them unmangled costs no crown protection
# and keeps the interface stable. Private names in these modules are still mangled.
_CONTRACT_MODULES: frozenset[str] = frozenset({
    "bundle", "metrics", "sqlite_setup", "license", "measure",
})


def _py_files(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            out.extend(sorted(path.rglob("*.py")))
        elif path.suffix == ".py":
            out.append(path)
    return out


def _collect(trees: dict[Path, ast.AST]) -> set[str]:
    """The FUNCTION/CLASS names safe to rename: defined exactly once across the whole
    program, appearing in no string literal, not a dunder, not excluded, not a public
    name of a cross-package CONTRACT module — AND either PRIVATE (leading `_`, never
    called by a framework) or a PUBLIC module-level FUNCTION or CLASS. PUBLIC METHODS are
    left alone: a class deriving from starlette/pydantic can have a method called by the
    framework via duck-typing, and that call lives in the framework's code, not ours, so
    our string-scan would not see it."""
    def_counts: dict[str, int] = {}
    strings: set[str] = set()
    public_methods: set[str] = set()
    runtime_fields: set[str] = set()
    contract_public: set[str] = set()
    for path, tree in trees.items():
        in_contract = path.stem in _CONTRACT_MODULES
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    # A function elsewhere can share a dataclass/Pydantic field's
                    # spelling. visit_Name rewrites annotation targets too, but
                    # generated __init__ and arbitrary receiver.field use the public
                    # spelling. Such a name is not globally safe to rename at all.
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                        runtime_fields.add(item.target.id)
                    if (isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                            and not item.name.startswith("_")):
                        public_methods.add(item.name)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if not node.name.startswith("__"):
                    def_counts[node.name] = def_counts.get(node.name, 0) + 1
                    if in_contract and not node.name.startswith("_"):
                        contract_public.add(node.name)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                strings.add(node.value)
    out: set[str] = set()
    for name, count in def_counts.items():
        if (count != 1 or name in strings or name in _EXCLUDE
                or name in contract_public or name in runtime_fields):
            continue
        if name.startswith("_") or name not in public_methods:
            out.add(name)
    return out


def _our_refs(trees: dict, stems: set[str]) -> set[str]:
    """Names that denote OUR code: `self`/`cls`, our submodule names, and anything bound
    by a pseudex import. `obj.attr` is renamed only when `obj` is one of these — so a
    cross-module `morph_places.to_nominative` is rewritten, but a stdlib `re.escape` whose
    method name happens to collide with one of ours is left untouched.

    ЛОКАЛЬНЫЙ АЛИАС МОДУЛЯ — ЧАСТЬ ТОГО ЖЕ ПРАВИЛА, и без него пасс ломает продукт
    молча. `ru_pii.py` пишет `v6 = ru_pii_v6` (импорт внутри функции, чтобы разорвать
    цикл) и дальше зовёт `v6.detect_checksum_anchored(...)`. По имени `v6` нельзя
    понять, что это наш модуль, поэтому `def` уезжал в `_z0xxx`, а вызов оставался под
    старым именем — и падал `AttributeError` в СОБРАННОМ образе, на старте sidecar, то
    есть там, где диагностика стоит получаса Nuitka. Транзитивное замыкание по
    присваиванию закрывает и `v6 = ru_pii_v6`, и цепочки `m = mod; x = m`."""
    refs: set[str] = {"self", "cls"} | set(stems)
    for tree in trees.values():
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("pseudex"):
                for a in node.names:
                    refs.add(a.asname or a.name)
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.startswith("pseudex"):
                        refs.add(a.asname or a.name.split(".")[0])
    # ЗАМЫКАНИЕ ПО ПРИСВАИВАНИЮ: `alias = <имя, которое уже наше>` делает алиас нашим.
    # AnnAssign покрыт тем же правилом (`v6: ModuleType = ru_pii_v6`).
    added = True
    while added:
        added = False
        for tree in trees.values():
            for node in ast.walk(tree):
                value: ast.expr | None = None
                targets: list[ast.expr] = []
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Name):
                    value, targets = node.value, list(node.targets)
                elif (isinstance(node, ast.AnnAssign) and isinstance(node.value, ast.Name)
                        and node.target is not None):
                    value, targets = node.value, [node.target]
                if value is None or value.id not in refs:
                    continue
                for target in targets:
                    if isinstance(target, ast.Name) and target.id not in refs:
                        refs.add(target.id)
                        added = True
    return refs


class _Renamer(ast.NodeTransformer):
    def __init__(self, mapping: dict[str, str], our_refs: set[str]) -> None:
        self._m = mapping
        self._our = our_refs

    def _rename(self, name: str) -> str:
        return self._m.get(name, name)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        node.name = self._rename(node.name)
        return self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        node.name = self._rename(node.name)
        return self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> ast.AST:
        # A bare name refers to our def or a local — never to `re.escape` (that is an
        # Attribute). Safe to rename by name.
        node.id = self._rename(node.id)
        return node

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        self.generic_visit(node)
        if (node.attr in self._m and isinstance(node.value, ast.Name)
                and node.value.id in self._our):
            node.attr = self._m[node.attr]
        return node

    def visit_alias(self, node: ast.alias) -> ast.AST:
        # `from x import _name` / `import x as _name` — rename the imported name and any
        # local alias; whole-program so the def moved too.
        node.name = self._rename(node.name)
        if node.asname:
            node.asname = self._rename(node.asname)
        return node


def main(paths: list[str]) -> int:
    files = _py_files(paths)
    trees = {f: ast.parse(f.read_text(encoding="utf-8")) for f in files}
    stems = {f.stem for f in files}
    our_refs = _our_refs(trees, stems)
    candidates = sorted(_collect(trees))
    mapping = {name: f"_z{i:04d}" for i, name in enumerate(candidates)}
    mangled: dict[Path, str] = {}
    for f, tree in trees.items():
        new_tree = ast.fix_missing_locations(_Renamer(mapping, our_refs).visit(tree))
        out = ast.unparse(new_tree)
        ast.parse(out)  # the mangled source must still parse
        mangled[f] = out
    # САМОПРОВЕРКА, И ОНА ЖЕ — ЕДИНСТВЕННОЕ, ЧТО ЛОВИТ ЭТОТ КЛАСС ДЕФЕКТА ДО ОБРАЗА.
    # `ast.parse` выше доказывает, что мангленный файл — синтаксически питон; он НЕ
    # доказывает, что вызов нашёл своё определение. Ровно так пасс и ломал продукт:
    # `v6.detect_checksum_anchored` остался старым именем рядом с переименованным
    # `def`, синтаксис цел, а sidecar падал `AttributeError` на старте.
    #
    # И СВОЙ НАБОР БАЗ, НЕЗАВИСИМЫЙ ОТ `our_refs`. Это не дублирование ради
    # дублирования: `v6` не попал в `our_refs` — ЭТО И ЕСТЬ причина дефекта, и
    # проверка, спрашивающая `our_refs`, ослепла бы ровно там, где нужно зрение
    # (первая версия этой строки так и молчала). Свидетель считает сам: наши модули —
    # это стемы файлов, алиас — присваивание имени, которое уже нашим является.
    # Считаются ТОЛЬКО модули и их алиасы, без `self`/`cls`: база `self` потянула бы
    # `self.attr` на чужом методе и превратила бы проверку в источник ложных отказов.
    module_bases: set[str] = set(stems)
    for tree in trees.values():
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("pseudex"):
                for a in node.names:
                    module_bases.add(a.asname or a.name)
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.startswith("pseudex"):
                        module_bases.add(a.asname or a.name.split(".")[0])
    grew = True
    while grew:
        grew = False
        for tree in trees.values():
            for node in ast.walk(tree):
                src: ast.expr | None = None
                dst: list[ast.expr] = []
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Name):
                    src, dst = node.value, list(node.targets)
                elif (isinstance(node, ast.AnnAssign) and isinstance(node.value, ast.Name)
                        and node.target is not None):
                    src, dst = node.value, [node.target]
                if src is None or src.id not in module_bases:
                    continue
                for target in dst:
                    if isinstance(target, ast.Name) and target.id not in module_bases:
                        module_bases.add(target.id)
                        grew = True
    dangling: list[str] = []
    for f, out in mangled.items():
        for node in ast.walk(ast.parse(out)):
            if (isinstance(node, ast.Attribute) and node.attr in mapping
                    and isinstance(node.value, ast.Name)
                    and node.value.id in module_bases):
                dangling.append(f"{f.name}:{node.lineno}: {node.value.id}.{node.attr}")
    if dangling:
        print("mangle left dangling references — refusing to write:", file=sys.stderr)
        for line in dangling[:20]:
            print(f"  {line}", file=sys.stderr)
        return 1
    for f, out in mangled.items():
        f.write_text(out + "\n", encoding="utf-8")
    print(f"mangled {len(mapping)} private crown symbols across {len(files)} files "
          f"(e.g. {candidates[:3]} -> _z0000..)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or ["./pseudex", "./serve_main.py"]))
