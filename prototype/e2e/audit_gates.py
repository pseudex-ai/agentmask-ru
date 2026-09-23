"""Which of our gates cannot fail — the whole roster, mechanically.

WHY THIS EXISTS. Eight defects of one shape were found by hand this week, and
every one of them was a check that could not go red: `P1` proved the absence of
four strings out of 573 and would have passed grepping a missing file; `L12`
asserts `requests > 0` after making twelve calls, so an engine billing one in
twelve passes the only gate that guards the invoice; a benchmark triple with
nothing to compare cleared all five levels because `not any([])` is True. Reading
harder is not the answer to that — the reason all eight survived review is that
each one READS correctly. What separates them is a property of the verdict
expression, and a property is checkable.

THE PROPERTY. A verdict is made of atoms, and an atom is POSITIVE when it needs
evidence to exist (`x in output`, `code == 200`, `bool(rows)`) or NEGATIVE when
it is satisfied by nothing at all (`x not in output`, `not rows`, `count == 0`).
A gate assembled only from negative atoms passes on an empty world: the container
that never started, the grep that could not open its file, the log that was
rotated away. Such a gate is not weak, it is decorative.

PAIRED BY SOURCE, WHICH IS THE PART THAT TAKES A TOOL. "Has a positive atom
somewhere" is too coarse and would clear `L19`, whose positives read the vault
and the directory listing while its one negative reads a grep that nothing
proves works. The rule this file enforces is narrower: EVERY negative atom needs
a positive atom OVER THE SAME SOURCE — the same function call, traced back
through local assignments. `L20` greps for plaintext, finds it, then greps again
after the migration and requires nothing; that is the same instrument answering
both ways, and it is the shape every negative assertion should have.

WHAT IT DELIBERATELY DOES NOT DO. It cannot tell whether a threshold is the
right number (`>= 2` workers is meaningful, `> 0` requests is not), so it reports
thresholds and lets a person decide. It cannot know that a source is
untrustworthy for reasons outside the file. It flags shapes, and a flagged gate
is a question, not a verdict.

AND IT CARRIES ITS OWN POSITIVE CONTROL, because a checker for checks that cannot
fail must not be one. `--selftest` runs the classifier over a fixture holding
known-bad and known-good gates and refuses to report a clean roster unless it
separates them.

usage:
    python3 e2e/audit_gates.py                 # the roster, exit 1 if anything is flagged
    python3 e2e/audit_gates.py --selftest      # prove the analyser can tell them apart
    python3 e2e/audit_gates.py --quiet         # findings only
"""

import argparse
import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

_HERE = Path(__file__).resolve().parent

# The files whose `gate(...)` verdicts this audits. Both roster files, and the
# metering attack suite, which makes the same kind of claim about the same kind
# of evidence.
TARGETS = ("e2e/gates.py", "e2e/pack_gates.py", "e2e/slot_gates.py")

# `x == 0` is the count of nothing — but `proc.returncode == 0` is a command
# that RAN AND SUCCEEDED, which an empty world cannot produce. Same literal,
# opposite meanings, and the operand's name is the only thing that separates
# them. Getting this wrong made the first run flag four healthy terms in P6.
_EXIT_CODE_WORDS = ("returncode", "status_code", "exit", "code")
_COUNT_WORDS = ("count", "hits", "errors", "len", "size", "total", "n_")

POSITIVE = "positive"
NEGATIVE = "negative"
THRESHOLD = "threshold"
UNKNOWN = "unknown"

# Shell fragments that turn a failed command into an empty success. A negative
# atom reading a source built out of one of these is the `P1` defect exactly:
# the command never ran, the output is empty, and empty means clean.
SILENT_SHELL = ("|| true", "2>/dev/null", "2>&1 || true")

# CALLEES THAT IDENTIFY NOTHING. The source of an atom is meant to name the
# INSTRUMENT that produced it, so that a negative assertion can be paired with a
# positive one over the same instrument. `httpx.get` is not an instrument, it is
# the transport every instrument uses — counting it made `entity_types <= local`
# pair with an unrelated term in L12 that also happened to fetch something over
# HTTP, and the subset hole stayed invisible. Same for the builtins that merely
# reshape a value they were handed.
GENERIC_CALLEES = frozenset({
    "httpx.get", "httpx.post", "httpx.put", "httpx.delete", "get", "json",
    "json.loads", "json.dumps", "set", "len", "int", "float", "str", "bool",
    "sorted", "list", "dict", "join", "split", "splitlines", "strip", "lower",
    "read_text", "values", "keys", "items", "format", "range",
})


@dataclass
class Atom:
    kind: str
    text: str
    sources: frozenset[str]


@dataclass
class GateFinding:
    file: str
    line: int
    func: str
    label: str
    atoms: list[Atom]
    flags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.flags


def _literal_is_empty(node: ast.AST) -> bool:
    """Is this literal the value an absent thing would produce?"""
    if isinstance(node, ast.Constant):
        return node.value in (0, "", None, False)
    if isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
        return not getattr(node, "elts", getattr(node, "keys", [1]))
    return False


class _Resolver:
    """Local names back to the expressions that produced them.

    A verdict is almost never written inline — it is `ok = a and b and c`, and
    `a` was assigned eight lines up from a call. Without following that, every
    atom classifies as UNKNOWN and the audit says nothing.
    """

    def __init__(self, func: ast.FunctionDef):
        self.assigns: dict[str, ast.expr] = {}
        for node in ast.walk(func):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.assigns.setdefault(target.id, node.value)
                    # `code, output = run_disposable_sidecar(...)` — without this
                    # both names resolve to nothing, every atom over them reads
                    # source `[]`, and the pairing rule has nothing to pair.
                    elif isinstance(target, (ast.Tuple, ast.List)):
                        for element in target.elts:
                            if isinstance(element, ast.Name):
                                self.assigns.setdefault(element.id, node.value)
            elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)):
                target = node.target
                if isinstance(target, ast.Name) and node.value is not None:
                    self.assigns.setdefault(target.id, node.value)

    def expand(self, node: ast.expr, depth: int = 0) -> ast.expr:
        """One name -> the expression behind it, while it stays a bare name."""
        seen: set[str] = set()
        while isinstance(node, ast.Name) and node.id in self.assigns and depth < 8:
            if node.id in seen:
                break
            seen.add(node.id)
            node = self.assigns[node.id]
            depth += 1
        return node

    def sources(self, node: ast.expr, depth: int = 0) -> frozenset[str]:
        """Which CALLS this expression's value ultimately came from.

        The identity of a source is the callee's name — `readable_pii_in_data`,
        `logs`, `httpx.get`. Coarse on purpose: two different greps through the
        same helper are the same instrument, and that is the question being
        asked. Names that resolve to nothing contribute themselves, so a value
        arriving as a parameter still pairs with itself.
        """
        if depth > 8:
            return frozenset()
        found: set[str] = set()
        node = self.expand(node, depth)
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                name = _callee_name(child.func)
                if name and name.split(".")[-1] not in GENERIC_CALLEES \
                        and name not in GENERIC_CALLEES:
                    found.add(name)
            elif isinstance(child, ast.Name) and child.id in self.assigns:
                if child is not node:
                    found |= self.sources(child, depth + 1)
            elif isinstance(child, ast.Name):
                found.add(f"name:{child.id}")
        return frozenset(found)


def _callee_name(func: ast.AST) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        base = _callee_name(func.value)
        return f"{base}.{func.attr}" if base else func.attr
    return ""


def _split_terms(node: ast.expr, resolver=None, depth: int = 0) -> list[ast.expr]:
    """Flatten `a and b and (c or d)` into its atoms.

    `or` is flattened too. That is deliberately generous — an `or` branch is a
    way for a verdict to be reached without the other branch's evidence — and it
    means a gate needs a positive atom in each branch to look healthy.
    """
    if isinstance(node, ast.BoolOp):
        out: list[ast.expr] = []
        for value in node.values:
            out.extend(_split_terms(value, resolver, depth + 1))
        return out
    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        return [node]
    # A NAME STANDING FOR A CONJUNCTION IS ITS PARTS. Without this the splitter
    # stops at `both_services` and never sees the two membership tests behind
    # it, so a gate that HAS a positive control still reads as having none.
    if resolver is not None and isinstance(node, ast.Name) and depth < 6:
        expanded = resolver.expand(node)
        if isinstance(expanded, ast.BoolOp):
            return _split_terms(expanded, resolver, depth + 1)
    return [node]


def _classify(node: ast.expr, resolver: _Resolver) -> tuple[str, frozenset[str]]:
    """POSITIVE / NEGATIVE / THRESHOLD, plus where the evidence came from."""
    # `not X` is negative, and the source is X's.
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return NEGATIVE, resolver.sources(node.operand)

    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        op = node.ops[0]
        left, right = node.left, node.comparators[0]
        # Membership: the HAYSTACK is the evidence, whichever way it is asserted.
        if isinstance(op, ast.In):
            return POSITIVE, resolver.sources(right)
        if isinstance(op, ast.NotIn):
            return NEGATIVE, resolver.sources(right)
        if isinstance(op, (ast.Is, ast.IsNot)):
            empty = isinstance(right, ast.Constant) and right.value is None
            kind = NEGATIVE if (isinstance(op, ast.Is) and empty) else POSITIVE
            return kind, resolver.sources(left)
        if isinstance(op, (ast.Eq, ast.NotEq)):
            sources = resolver.sources(left) | resolver.sources(right)
            if isinstance(op, ast.NotEq):
                return UNKNOWN, sources
            empty = _literal_is_empty(right) or _literal_is_empty(left)
            if not empty:
                return POSITIVE, sources
            subject = ast.unparse(left).lower() + ast.unparse(right).lower()
            if any(word in subject for word in _EXIT_CODE_WORDS):
                return POSITIVE, sources
            if any(word in subject for word in _COUNT_WORDS):
                return NEGATIVE, sources
            return UNKNOWN, sources
        if isinstance(op, (ast.Gt, ast.GtE)):
            bound = right
            zeroish = isinstance(bound, ast.Constant) and bound.value in (0, 1)
            kind = THRESHOLD if zeroish else POSITIVE
            return kind, resolver.sources(left)
        if isinstance(op, (ast.Lt, ast.LtE)):
            # `set() <= anything` is True, and that is the L12 subset shape. A
            # BUDGET (`size_gb < 1.5`) is a different animal: an empty world does
            # not produce a small number there, it raises on the way. Only the
            # collection form is satisfied by nothing.
            if isinstance(right, ast.Constant) or isinstance(left, ast.Constant):
                return UNKNOWN, resolver.sources(left)
            # ARITHMETIC CANNOT BE SATISFIED BY NOTHING. `p50_ratio <= bound`
            # looks like the subset shape and is not one: an empty world does
            # not hand P4 a small ratio, it raises on the division long before
            # the comparison. Only a comparison of two CONTAINERS is satisfied
            # by the empty one.
            if any(isinstance(n, ast.BinOp)
                   for side in (left, right)
                   for n in ast.walk(resolver.expand(side))):
                return UNKNOWN, resolver.sources(left)
            return NEGATIVE, resolver.sources(left)

    expanded = resolver.expand(node)
    if expanded is not node:
        kind, sources = _classify(expanded, resolver)
        return kind, sources or resolver.sources(node)

    if isinstance(node, ast.Call):
        name = _callee_name(node.func)
        if name in ("bool", "any", "len"):
            return POSITIVE, resolver.sources(node.args[0]) if node.args else frozenset()
        # `all(...)` over an empty iterable is True. That is vacuous truth, and
        # it is how a benchmark reported 18/18 having made no call at all.
        if name == "all":
            return NEGATIVE, resolver.sources(node.args[0]) if node.args else frozenset()
        return POSITIVE, resolver.sources(node)

    if isinstance(node, ast.Name):
        return UNKNOWN, resolver.sources(node)

    return UNKNOWN, resolver.sources(node)


def _silent_sources(tree: ast.Module) -> set[str]:
    """Helpers whose shell swallows its own failure.

    A negative atom over one of these is the sharpest form of the defect: the
    command is allowed to fail, the output is empty, and the gate reads empty as
    proof of absence.
    """
    silent: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        body = ast.dump(node)
        for const in (n.value for n in ast.walk(node)
                      if isinstance(n, ast.Constant) and isinstance(n.value, str)):
            if any(fragment in const for fragment in SILENT_SHELL):
                silent.add(node.name)
                break
        else:
            if "JoinedStr" in body and any(
                    fragment in (n.value or "")
                    for n in ast.walk(node)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)
                    for fragment in SILENT_SHELL):
                silent.add(node.name)
    return silent


def audit_source(source: str, filename: str) -> list[GateFinding]:
    tree = ast.parse(source)
    silent = _silent_sources(tree)
    findings: list[GateFinding] = []

    for func in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        resolver = _Resolver(func)
        for call in [n for n in ast.walk(func) if isinstance(n, ast.Call)]:
            if _callee_name(call.func) != "gate" or len(call.args) < 2:
                continue
            label = call.args[0].value if isinstance(call.args[0], ast.Constant) else "?"
            verdict = call.args[1]
            atoms: list[Atom] = []
            for term in _split_terms(resolver.expand(verdict), resolver):
                kind, sources = _classify(term, resolver)
                atoms.append(Atom(kind, ast.unparse(term)[:88], sources))
                # A CONDITION HANDED TO A HELPER IS STILL PART OF THE VERDICT,
                # and the first version of this file could not see one. `L12`
                # makes twelve calls and then waits for
                # `wait_until(lambda: usage["requests"] > 0, ...)`: the atom in
                # the verdict is the healthy-looking `reported`, and the
                # threshold that lets an engine bill one request in twelve sits
                # inside the lambda. Missing the one defect already known by
                # hand would have made this analyser exactly the kind of check
                # it exists to find.
                for lam in [n for n in ast.walk(resolver.expand(term))
                            if isinstance(n, ast.Lambda)]:
                    for inner in _split_terms(lam.body, resolver):
                        kind, sources = _classify(inner, resolver)
                        atoms.append(Atom(kind, f"(in lambda) {ast.unparse(inner)[:76]}",
                                          sources))

            finding = GateFinding(filename, call.lineno, func.name, str(label), atoms)
            positives = {s for a in atoms if a.kind == POSITIVE for s in a.sources}
            has_positive = any(a.kind == POSITIVE for a in atoms)
            negatives = [a for a in atoms if a.kind == NEGATIVE]

            # A verdict that is a bare literal `False` is an early return with a
            # reason, not a claim about the product. Those are healthy.
            if len(atoms) == 1 and isinstance(_split_terms(verdict, resolver)[0], ast.Constant):
                continue

            if negatives and not has_positive:
                finding.flags.append("NO POSITIVE CONTROL: every term passes on empty evidence")
            for atom in negatives:
                if atom.sources and not (atom.sources & positives):
                    finding.flags.append(
                        f"UNGUARDED NEGATIVE: `{atom.text}` reads "
                        f"{sorted(atom.sources & _real(atom.sources))[:3]} "
                        f"which no positive term proves works")
                # Only when the negative is ALSO unguarded. A helper whose
                # shell swallows failure is fine once it demonstrates it found
                # something — that is exactly the repair, and flagging it after
                # would train the reader to ignore the flag.
                if (atom.sources & silent) and not (atom.sources & positives):
                    finding.flags.append(
                        f"SILENT SOURCE: `{atom.text}` reads "
                        f"{sorted(atom.sources & silent)}, whose shell hides its own failure")
            for atom in atoms:
                if atom.kind == THRESHOLD:
                    # NOT a failure: `hits > 0` on a memory scan is the right
                    # assertion (presence is the whole claim), while
                    # `requests > 0` after twelve calls is the billing hole.
                    # The shape is identical and only the gate's author knows
                    # which it is, so this asks rather than judges.
                    finding.notes.append(
                        f"THRESHOLD: `{atom.text}` accepts any non-zero amount — "
                        f"assert the count if the gate knows it")
            findings.append(finding)
    return findings


def _real(sources: frozenset[str]) -> frozenset[str]:
    """Drop the `name:` placeholders — they are noise in a message."""
    return frozenset(s for s in sources if not s.startswith("name:"))


# --- the analyser's own positive control ---------------------------------

_FIXTURE = '''
def gate_decorative():
    """Every term passes on nothing: the classic."""
    output = sidecar_exec(["sh", "-c", "ls /app/pseudex 2>&1 || true"]).stdout
    ok = "pseudex" not in output and "secret" not in output
    return gate("D decorative", ok, "")

def gate_threshold():
    for _ in range(12):
        post_mask(90)
    usage = fetch_usage()
    ok = usage["requests"] > 0
    return gate("T threshold", ok, "")

def gate_unguarded():
    held = [v for v in payload.values() if v in restored()]
    leaked = readable_pii_in_data()
    return gate("U unguarded", bool(held) and not leaked, "")

def gate_paired():
    plain_hits = readable_pii_in_data()
    encrypted_hits = readable_pii_in_data()
    return gate("G paired", bool(plain_hits) and not encrypted_hits, "")

def gate_healthy():
    page = http_get("/")
    ok = page.status_code == 200 and len(page.body) >= 100
    return gate("H healthy", ok, "")

def gate_exit_code():
    """`returncode == 0` is a command that RAN. The first version of this
    analyser called it negative and flagged four healthy terms in P6."""
    signed = sh(["cosign", "sign"])
    verified = sh(["cosign", "verify"])
    ok = signed.returncode == 0 and verified.returncode == 0
    return gate("E exit code", ok, "")

def gate_budget():
    """A budget over a parsed measurement. An empty world raises on the way to
    the number, it does not quietly produce a small one."""
    size_gb = int(sh(["du"]).stdout.strip()) / 1e9
    return gate("B budget", size_gb < 1.5, "")

def gate_subset():
    """`set() <= anything` is True, and this is the shape L12 bills on."""
    remote = set(fetch_remote())
    local = set(fetch_local())
    return gate("S subset", remote <= local, "")

def gate_lambda_threshold():
    """The threshold hidden behind a helper — L12's actual shape."""
    for _ in range(12):
        post_mask(90)
    reported = wait_until(lambda: fetch_usage()["requests"] > 0, 60, 5, "a report")
    return gate("L lambda", reported, "")

def gate_coarse_transport():
    """Both terms travel over HTTP, and only one is evidence for the other's
    instrument. Counting the transport as the source paired them and hid the
    subset hole L12 actually has."""
    remote = httpx.get("/admin/usage").json()
    local = httpx.get("/usage").json()
    reported = wait_until(lambda: probe_reports(), 60, 5, "a report")
    entity_types = set(remote["entities"])
    local_types = set(local["counts"])
    return gate("C coarse", reported and entity_types <= local_types, "")

def gate_ratio_budget():
    """A ratio against a derived bound. The empty world raises on the division,
    it does not quietly produce a passing number — P4's real shape."""
    p50_ratio = compiled["p50"] / source["p50"]
    bound = max(1.25, noise * 2.0)
    return gate("R ratio", p50_ratio <= bound, "")

def gate_named_conjunction():
    """The positive control hides behind a name — L15's shape after its fix."""
    combined = all_logs()
    both_services = "sidecar" in combined and "license" in combined
    leaked = [v for v in leak_values() if v in combined]
    return gate("N named", both_services and not leaked, "")

def gate_unpacked():
    """Tuple targets: without them both names resolve to nothing and the
    pairing rule has nothing to pair."""
    code, output = run_disposable_sidecar(image, {}, 150)
    return gate("P unpacked", "license_missing" not in output, "")
'''

_EXPECTED = {
    "D decorative": "NO POSITIVE CONTROL",
    "T threshold": "THRESHOLD",
    "U unguarded": "UNGUARDED NEGATIVE",
    "G paired": None,
    "H healthy": None,
    "E exit code": None,
    "B budget": None,
    "S subset": "UNGUARDED NEGATIVE",
    "L lambda": "THRESHOLD",
    "C coarse": "UNGUARDED NEGATIVE",
    "R ratio": None,
    "N named": None,
    "P unpacked": "UNGUARDED NEGATIVE",
}


def selftest() -> bool:
    findings = {f.label: f for f in audit_source(_FIXTURE, "<fixture>")}
    ok = True
    for label, expected in _EXPECTED.items():
        finding = findings.get(label)
        if finding is None:
            print(f"  FAIL  {label}: the analyser did not even see this gate")
            ok = False
            continue
        joined = " | ".join(finding.flags)
        if expected is None:
            good = finding.ok
            detail = joined or "clean"
        else:
            good = any(expected in line
                       for line in finding.flags + finding.notes)
            detail = " | ".join(finding.flags + finding.notes) or "nothing flagged"
        print(f"  {'PASS' if good else 'FAIL'}  {label}: {detail}")
        ok = ok and good
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--files", nargs="*", default=list(TARGETS))
    args = parser.parse_args()

    print("== analyser self-test ==")
    if not selftest():
        print("\nTHE ANALYSER CANNOT TELL A BROKEN GATE FROM A GOOD ONE. "
              "Its verdict on the real roster would mean nothing.")
        return 2
    if args.selftest:
        return 0

    root = _HERE.parent
    findings: list[GateFinding] = []
    for relative in args.files:
        path = root / relative
        findings.extend(audit_source(path.read_text(encoding="utf-8"), relative))

    flagged = [f for f in findings if not f.ok]
    print(f"\n== {len(findings)} verdicts across {len(args.files)} files ==")
    for finding in findings:
        if finding.ok and not finding.notes and args.quiet:
            continue
        mark = "ok  " if finding.ok else "FLAG"
        print(f"\n  {mark} {finding.file}:{finding.line}  {finding.label}")
        if not args.quiet:
            for atom in finding.atoms:
                print(f"         {atom.kind:<9} {atom.text}")
        for flag in finding.flags:
            print(f"         -> {flag}")
        for note in finding.notes:
            print(f"         ?  {note}")

    print("\n" + "=" * 70)
    print(f"{len(findings) - len(flagged)}/{len(findings)} verdicts carry a "
          f"positive control over every source they read")
    if not findings:
        print("NO VERDICT WAS ANALYSED. The `gate(...)` call shape must have changed.")
        return 1
    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main())
