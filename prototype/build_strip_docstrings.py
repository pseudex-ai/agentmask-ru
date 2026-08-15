"""Remove docstrings from our own sources before they are compiled.

WHY THIS EXISTS RATHER THAN `--python-flag=no_docstrings`: that flag is real and
we pass it, but it only stops the compiled module from SETTING `__doc__` — the
string literals still end up in Nuitka's constants blob, and
`grep -a "Connector to the leased asset state" pseudex-serve` finds them.

That matters more than the code itself. This repo's docstrings are the design
record: they say which alternative was rejected and why, what was measured, and
where the sharp edges are. Shipping them is handing over the reasoning while
withholding only the syntax.

HOW: each docstring's exact source span is replaced with `""`, padded with
newlines so the file keeps its original line count. Two consequences, both
wanted:

  * an expression statement remains, so a body that contained nothing but a
    docstring is still syntactically valid without inserting `pass`;
  * line numbers do not move, so a traceback from the shipped binary still
    points at the right line of the real source when we debug a customer issue.

Applied ONLY to our own tree. Third-party packages are left alone: some of them
use `__doc__` functionally (argparse/click help, FastAPI's OpenAPI text), and
breaking them to protect prose we did not write is a bad trade.

usage: python3 build_strip_docstrings.py <dir-or-file> [more...]
"""

import ast
import sys
from pathlib import Path


def _docstring_nodes(tree: ast.AST) -> list[ast.Constant]:
    """Every module/class/function docstring node in the tree."""
    found: list[ast.Constant] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            found.append(first.value)
    return found


def strip_text(source: str) -> tuple[str, int]:
    """Return (source without docstring contents, how many were removed)."""
    tree = ast.parse(source)
    nodes = _docstring_nodes(tree)
    if not nodes:
        return source, 0

    lines = source.splitlines(keepends=True)
    # Last span first, so earlier spans keep their original offsets.
    for node in sorted(nodes, key=lambda n: (n.lineno, n.col_offset), reverse=True):
        start_line, end_line = node.lineno - 1, node.end_lineno - 1
        # `col_offset` is a UTF-8 BYTE offset, not a character index — slicing the
        # str directly silently mis-cuts every line containing non-ASCII, and this
        # codebase's docstrings are full of Cyrillic and em-dashes. The symptom was
        # a "fixed" file whose replacement swallowed the following line.
        head = lines[start_line].encode("utf-8")[:node.col_offset].decode("utf-8")
        tail = lines[end_line].encode("utf-8")[node.end_col_offset:].decode("utf-8")
        # Keep the file's line count identical so tracebacks stay truthful.
        padding = "\n" * (end_line - start_line)
        lines[start_line:end_line + 1] = [f'{head}""{padding}{tail}']
    return "".join(lines), len(nodes)


def strip_file(path: Path) -> int:
    source = path.read_text(encoding="utf-8")
    stripped, count = strip_text(source)
    if count:
        # Parse the RESULT before writing it. A transform that produces invalid
        # Python must fail the build here, loudly, rather than surface as a
        # mystery compile error thousands of lines into the Nuitka output.
        ast.parse(stripped)
        path.write_text(stripped, encoding="utf-8")
    return count


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    total_files = total_docstrings = 0
    for argument in sys.argv[1:]:
        target = Path(argument)
        paths = sorted(target.rglob("*.py")) if target.is_dir() else [target]
        for path in paths:
            removed = strip_file(path)
            if removed:
                total_files += 1
                total_docstrings += removed
    print(f"stripped {total_docstrings} docstrings from {total_files} file(s)",
          file=sys.stderr)


if __name__ == "__main__":
    main()
