"""Release preprocessing must not rename runtime dataclass/Pydantic field names.

The compiled inspection HTTP gate found this: vault_key.replacement was a unique
public function, so a class annotation named replacement was renamed too, while
piece.replacement still read the public field. Syntax stayed valid; /mask died.
"""

import ast
import dataclasses
import sys
import types
from pathlib import Path

import build_mangle_names as mangle


SOURCE = '''
from dataclasses import dataclass

def replacement(value):
    return value

@dataclass(frozen=True)
class Piece:
    length: int
    replacement: str | None = None

piece = Piece(7, "synthetic")
answer = piece.replacement
'''


def main():
    tree = ast.parse(SOURCE)
    paths = {Path("fixture.py"): tree}
    candidates = mangle._collect(paths)
    assert "replacement" not in candidates, "class field also named a function is not a safe rename"
    mapping = {name: f"_test_{index}" for index, name in enumerate(sorted(candidates))}
    renamed = ast.fix_missing_locations(mangle._Renamer(mapping, {"self", "cls"}).visit(tree))
    module = types.ModuleType("_mangle_field_fixture")
    sys.modules[module.__name__] = module
    try:
        exec(compile(renamed, "fixture.py", "exec"), module.__dict__)
        assert module.answer == "synthetic"
        assert dataclasses.asdict(module.piece) == {"length": 7, "replacement": "synthetic"}
        assert module.piece.replacement == "synthetic"
    finally:
        del sys.modules[module.__name__]
    print("PASS release preprocessing preserves annotated runtime field names")


if __name__ == "__main__":
    main()
