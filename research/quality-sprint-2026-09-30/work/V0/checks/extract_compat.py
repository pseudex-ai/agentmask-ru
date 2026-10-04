#!/usr/bin/env python3
"""V0 read-only extraction of the v5/v6 overlap matrix.

Pure stdlib. Runs `git show`/`git diff` READ-ONLY against the two frozen
commits; writes nothing outside work/V0/. No engine, no provider, no merge,
no checkout, no worktree mutation.

Usage: prototype/.venv/bin/python work/V0/checks/extract_compat.py
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path("/Users/igor/Projects/Obscura-hop-audit")
OUT = ROOT / "research/quality-sprint-2026-09-30/work/V0"
BASE = "3be526a2bfb8a9b9e86a9b14b3e11758f723f3a8"
V5 = "0bfda2363ef1a1d552e2ac093129b1026a86ad68"
V6 = "fad9c7466ea1221282214e6c747ca373ee7e6a55"
EVIDENCE_COMMIT = "890c50849a326f882eac336ba4e38c91171de473"

DECLARED_OVERLAP = json.loads(
    (ROOT / "research/hop-format-audit/next-sprint-review/v6-snapshot/"
     "branch-comparison.json").read_text())["overlapping_paths"]


def git(*args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} exited {proc.returncode}: {proc.stderr[:400]}")
    return proc.stdout


def names(ref_a: str, ref_b: str) -> list[str]:
    return git("diff", "--name-only", f"{ref_a}..{ref_b}").splitlines()


def top_level_symbols(text: str) -> set[str]:
    """Every module-level def/class/assignment name an AST can name."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set()
    out: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                for sub in ast.walk(t):
                    if isinstance(sub, ast.Name):
                        out.add(sub.id)
    return out


def symbols_at(ref: str, path: str) -> set[str]:
    try:
        text = git("show", f"{ref}:{path}")
    except SystemExit:
        return set()
    if path.endswith(".py"):
        return top_level_symbols(text)
    # A markdown file: its "symbols" are the headings and the code-spanned
    # identifiers a diff can name, so the same set algebra still applies.
    out: set[str] = set()
    for line in text.splitlines():
        if line.startswith("#"):
            out.add(line.strip("# ").strip())
        for match in re.finditer(r"`([A-Za-z_][A-Za-z0-9_./]{2,})`", line):
            out.add(match.group(1))
    return out


def main() -> int:
    log: list[str] = []

    def say(line: str) -> None:
        print(line)
        log.append(line)

    v5_changed = set(names(BASE, V5))
    v6_changed = set(names(BASE, V6))
    overlap = sorted(v5_changed & v6_changed)
    say(f"C1 overlap recomputed={len(overlap)} declared={len(DECLARED_OVERLAP)} "
        f"identical={overlap == sorted(DECLARED_OVERLAP)}")
    if overlap != sorted(DECLARED_OVERLAP):
        say("C1 MISMATCH — declared list is not reproducible from the refs")

    say(f"C2 v5_changed_vs_base={len(v5_changed)} v6_changed_vs_base={len(v6_changed)} "
        f"v6_only={len(v6_changed - v5_changed)} v5_only={len(v5_changed - v6_changed)}")

    proto_delta = git("diff", "--name-only", f"{V5}..{EVIDENCE_COMMIT}", "--", "prototype/")
    say(f"C3 product-source diff {V5[:7]}..{EVIDENCE_COMMIT[:7]} prototype/ files="
        f"{len(proto_delta.splitlines())} (expect 0)")

    rows = []
    for path in overlap:
        v5_syms = symbols_at(V5, path)
        v6_syms = symbols_at(V6, path)
        base_syms = symbols_at(BASE, path)
        added_v5 = sorted(v5_syms - base_syms)
        removed_v5 = sorted(base_syms - v5_syms)
        added_v6 = sorted(v6_syms - base_syms)
        removed_v6 = sorted(base_syms - v6_syms)
        numstat_v5 = git("diff", "--numstat", f"{BASE}..{V5}", "--", path).split()
        numstat_v6 = git("diff", "--numstat", f"{BASE}..{V6}", "--", path).split()
        both_removed = sorted(set(removed_v5) & set(removed_v6))
        rows.append({
            "path": path,
            "v5_stat": f"{numstat_v5[0]}/{numstat_v5[1]}" if numstat_v5 else "0/0",
            "v6_stat": f"{numstat_v6[0]}/{numstat_v6[1]}" if numstat_v6 else "0/0",
            "v5_added_symbols": added_v5,
            "v5_removed_symbols": removed_v5,
            "v6_added_symbols": added_v6,
            "v6_removed_symbols": removed_v6,
            "both_removed_symbols": both_removed,
        })
        say(f"C4 {path} v5+{len(added_v5)}/-{len(removed_v5)} v6+{len(added_v6)}/-{len(removed_v6)} "
            f"both_removed={len(both_removed)}")

    (OUT / "evidence" / "compat_raw.json").write_text(
        json.dumps({"v5": V5, "v6": V6, "base": BASE,
                    "overlap_count": len(overlap), "rows": rows},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    say(f"C5 wrote evidence/compat_raw.json rows={len(rows)}")
    (OUT / "evidence" / "extract_compat.log").write_text("\n".join(log) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
