"""The versions registry: which engine versions exist, which are supported, and
what a running container is told about its own (D-054…D-057, D-061).

    python3 -m licensing.registry validate ../deploy/releases.json
    python3 -m licensing.registry validate --previous <(git show HEAD~1:deploy/releases.json) ../deploy/releases.json
    python3 -m licensing.registry record --version 0.3.16 --digest sha256:… --date 2026-09-25 ../deploy/releases.json
    python3 -m licensing.registry aliases --version 0.3.16 ../deploy/releases.json
    python3 -m licensing.registry verdict --engine-version 0.3.14 ../deploy/releases.json

WHY A FILE IN THE REPOSITORY AND NOT A TABLE THE PIPELINE WRITES. The floor —
the oldest version the licence server still serves — is a security decision:
below it a customer's container stops masking. A decision like that goes
through review and the CI gate, so it lives in git, is changed by a pull
request, and reaches the server through a platform release. The pipeline is
allowed to `record` a new version (that is only ever additive); a human is
allowed to set `eol`, `eol_announced` and `notices`; nobody edits `latest` or
`digest` by hand.

WHY endoflife.date's SHAPE AND NOT ITS SITE. The site is Jekyll whose API is
generated at build time — Ruby for forty lines of JSON. The shape is the
value: cycles newest to oldest, per-cycle `eoas`/`eol`, a `latest` per cycle,
computed booleans on the way out.

WHAT THE SERVER OWES THE CONTAINER (D-055). Every lease response carries a
`version` block computed here: is this the newest, what is the newest in
your cycle, the floor, `deprecated_at` (RFC 9745, `@unix`, the day the
closing of your cycle was announced), `sunset_at` (RFC 8594, HTTP-date, the
day it closes), and an optional notice. The refusal (426) is computed here
too — `check()` — and it refuses to enforce a floor announced late (D-056):
a registry that sets `eol` without ninety days of notice is logged and
ignored, not obeyed. Docker 29.0 raised its floor faster than the ecosystem
and rolled it back in 29.3; the guard is that lesson as code.

Standard library only: the licensing server imports this, and so does the CI
gate, on a runner with nothing installed.
"""

import argparse
import datetime as dt
import json
import os
import re
import sys
import threading
from email.utils import format_datetime

SCHEMA = 1
STATES: tuple[str, ...] = ("current", "maintenance", "deprecated", "eol")
SEVERITIES: tuple[str, ...] = ("info", "warning", "danger")
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
_CYCLE_RE = re.compile(r"^\d+\.\d+$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class RegistryError(ValueError):
    """The registry file is not a registry we can act on."""


# ── parsing helpers ──────────────────────────────────────────────────────────

def version_tuple(version: str) -> tuple[int, int, int]:
    if not _VERSION_RE.match(version):
        raise RegistryError(f"not a version X.Y.Z: {version!r}")
    major, minor, patch = version.split(".")
    return int(major), int(minor), int(patch)


def cycle_of(version: str) -> str:
    major, minor, _ = version_tuple(version)
    return f"{major}.{minor}"


def _cycle_tuple(cycle: str) -> tuple[int, int]:
    major, minor = cycle.split(".")
    return int(major), int(minor)


def _date(value: object, field: str) -> dt.date | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _DATE_RE.match(value):
        raise RegistryError(f"{field}: not a date YYYY-MM-DD: {value!r}")
    return dt.date.fromisoformat(value)


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        doc = json.load(handle)
    if not isinstance(doc, dict):
        raise RegistryError("registry root is not an object")
    return doc


def dump(doc: dict, path: str) -> None:
    text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


# ── validation ───────────────────────────────────────────────────────────────

def validate(doc: dict, *, previous: dict | None, today: dt.date) -> list[str]:
    """Every way the file could lie, as a list of sentences. Empty = sound."""
    problems: list[str] = []

    def bad(message: str) -> None:
        problems.append(message)

    if doc.get("schema") != SCHEMA:
        bad(f"schema must be {SCHEMA}, got {doc.get('schema')!r}")
    if not isinstance(doc.get("product"), str) or not doc["product"]:
        bad("product must be a non-empty string")
    support = doc.get("support")
    if not isinstance(support, dict):
        bad("support must be an object")
        support = {}
    months = support.get("maintenance_months")
    notice_days = support.get("eol_notice_days")
    if not isinstance(months, int) or months <= 0:
        bad("support.maintenance_months must be a positive integer")
    if not isinstance(notice_days, int) or notice_days <= 0:
        bad("support.eol_notice_days must be a positive integer")
        notice_days = 0

    cycles = doc.get("cycles")
    if not isinstance(cycles, list) or not cycles:
        bad("cycles must be a non-empty list")
        return problems

    seen_aliases: dict[str, str] = {}
    order: list[tuple[int, int]] = []
    for index, cycle in enumerate(cycles):
        where = f"cycles[{index}]"
        if not isinstance(cycle, dict):
            bad(f"{where}: not an object")
            continue
        name = cycle.get("cycle")
        if not isinstance(name, str) or not _CYCLE_RE.match(name):
            bad(f"{where}: cycle must be X.Y, got {name!r}")
            continue
        order.append(_cycle_tuple(name))
        state = cycle.get("state")
        if state not in STATES:
            bad(f"{where} ({name}): state must be one of {STATES}, got {state!r}")
        try:
            release_date = _date(cycle.get("release_date"), f"{where}.release_date")
            eoas = _date(cycle.get("eoas"), f"{where}.eoas")
            eol = _date(cycle.get("eol"), f"{where}.eol")
            announced = _date(cycle.get("eol_announced"), f"{where}.eol_announced")
        except RegistryError as error:
            bad(str(error))
            continue
        if release_date is None:
            bad(f"{where} ({name}): release_date is required")

        latest = cycle.get("latest")
        if not isinstance(latest, dict):
            bad(f"{where} ({name}): latest must be an object")
        else:
            version = latest.get("version")
            if not isinstance(version, str) or not _VERSION_RE.match(version):
                bad(f"{where} ({name}): latest.version must be X.Y.Z, got {version!r}")
            elif cycle_of(version) != name:
                bad(f"{where} ({name}): latest.version {version} is not in this cycle")
            digest = latest.get("digest")
            if not isinstance(digest, str) or not _DIGEST_RE.match(digest):
                bad(f"{where} ({name}): latest.digest must be sha256:<64 hex>, got {digest!r}")
            try:
                _date(latest.get("date"), f"{where}.latest.date")
            except RegistryError as error:
                bad(str(error))

        aliases = cycle.get("aliases")
        if not isinstance(aliases, list) or not all(isinstance(a, str) for a in aliases):
            bad(f"{where} ({name}): aliases must be a list of strings")
            aliases = []
        if name not in aliases:
            bad(f"{where} ({name}): aliases must include the cycle itself ({name!r})")
        major = name.split(".")[0]
        for alias in aliases:
            if alias in seen_aliases:
                bad(f"{where} ({name}): alias {alias!r} already on cycle {seen_aliases[alias]}")
            seen_aliases[alias] = name
            if alias in (major, "latest") and index != 0:
                bad(f"{where} ({name}): alias {alias!r} belongs to the newest cycle only")
            if alias not in (name, major, "latest"):
                bad(f"{where} ({name}): unexpected alias {alias!r}")

        # State ↔ dates. `current` has no closing dates at all; anything past it
        # has `eoas`; `eol` state means the day has come.
        if state == "current" and (eoas is not None or eol is not None or announced is not None):
            bad(f"{where} ({name}): a current cycle carries no eoas/eol/eol_announced")
        if state in ("maintenance", "deprecated", "eol") and eoas is None:
            bad(f"{where} ({name}): state {state} requires eoas")
        if state == "eol" and (eol is None or eol > today):
            bad(f"{where} ({name}): state eol requires eol <= today ({today})")
        if state in ("maintenance", "deprecated") and eol is not None and eol <= today:
            bad(f"{where} ({name}): eol {eol} has passed but state is {state}")
        # The ninety-day rule (D-056): an eol without its announcement, or with
        # too little notice, is the Docker 29.0 mistake in a file.
        if eol is not None:
            if announced is None:
                bad(f"{where} ({name}): eol is set without eol_announced")
            else:
                if announced > today:
                    bad(f"{where} ({name}): eol_announced {announced} is in the future")
                if (eol - announced).days < notice_days:
                    bad(f"{where} ({name}): eol {eol} is less than {notice_days} days after eol_announced {announced}")
        if announced is not None and eol is None:
            bad(f"{where} ({name}): eol_announced without eol")

    if order != sorted(order, reverse=True):
        bad("cycles must be ordered newest to oldest")
    if len(set(order)) != len(order):
        bad("cycles must be unique")
    newest = cycles[0] if isinstance(cycles[0], dict) else {}
    if isinstance(newest, dict) and newest.get("state") not in ("current",):
        bad("the newest cycle must be current")

    notices = doc.get("notices")
    if not isinstance(notices, list):
        bad("notices must be a list")
    else:
        ids: set[str] = set()
        for index, notice in enumerate(notices):
            where = f"notices[{index}]"
            if not isinstance(notice, dict):
                bad(f"{where}: not an object")
                continue
            nid = notice.get("id")
            if not isinstance(nid, str) or not nid:
                bad(f"{where}: id required")
            elif nid in ids:
                bad(f"{where}: duplicate id {nid!r}")
            else:
                ids.add(nid)
            if notice.get("severity") not in SEVERITIES:
                bad(f"{where}: severity must be one of {SEVERITIES}")
            for field in ("applies_to", "text", "url"):
                if not isinstance(notice.get(field), str) or not notice[field]:
                    bad(f"{where}: {field} required")
            if isinstance(notice.get("applies_to"), str):
                try:
                    _parse_range(notice["applies_to"])
                except RegistryError as error:
                    bad(f"{where}: {error}")

    if previous is not None:
        problems.extend(_validate_against_previous(doc, previous))
    return problems


def _validate_against_previous(doc: dict, previous: dict) -> list[str]:
    """What a change is not allowed to do: rewrite history, move a digest,
    walk a version backwards. Additive is the only direction."""
    problems: list[str] = []
    before = {c.get("cycle"): c for c in previous.get("cycles", []) if isinstance(c, dict)}
    for cycle in doc.get("cycles", []):
        if not isinstance(cycle, dict):
            continue
        name = cycle.get("cycle")
        old = before.get(name)
        if old is None:
            continue
        old_latest = (old.get("latest") or {}) if isinstance(old.get("latest"), dict) else {}
        new_latest = (cycle.get("latest") or {}) if isinstance(cycle.get("latest"), dict) else {}
        try:
            old_v = version_tuple(str(old_latest.get("version", "0.0.0")))
            new_v = version_tuple(str(new_latest.get("version", "0.0.0")))
        except RegistryError:
            continue
        if new_v < old_v:
            problems.append(f"cycle {name}: latest.version went backwards {old_latest.get('version')} → {new_latest.get('version')}")
        if new_v == old_v and old_latest.get("digest") != new_latest.get("digest"):
            problems.append(f"cycle {name}: digest of {new_latest.get('version')} changed — a version is one artifact")
        if old.get("release_date") != cycle.get("release_date"):
            problems.append(f"cycle {name}: release_date rewritten")
    old_names = [c.get("cycle") for c in previous.get("cycles", []) if isinstance(c, dict)]
    new_names = [c.get("cycle") for c in doc.get("cycles", []) if isinstance(c, dict)]
    for name in old_names:
        if name not in new_names:
            problems.append(f"cycle {name} removed — a closed cycle stays listed as eol")
    return problems


# ── the questions the server and the pipeline ask ────────────────────────────

def _find_cycle(doc: dict, engine_version: str) -> dict | None:
    try:
        wanted = cycle_of(engine_version)
    except RegistryError:
        return None
    for cycle in doc["cycles"]:
        if cycle.get("cycle") == wanted:
            return cycle
    return None


def _cycle_for_verdict(doc: dict, engine_version: str) -> dict:
    """The cycle a version belongs to — or the OLDEST listed one when it
    belongs to none. "1.0.0" is what every pre-D-053 image reports, and a
    version outside every cycle is by definition something we no longer
    describe: reading it as newer than the newest would make the floor
    arithmetic call it fine."""
    found = _find_cycle(doc, engine_version)
    return found if found is not None else doc["cycles"][-1]


def floor(doc: dict, today: dt.date) -> str:
    """The oldest still-served version: `latest` of the oldest cycle whose
    `eol` has not passed."""
    for cycle in reversed(doc["cycles"]):
        eol = _date(cycle.get("eol"), "eol")
        if eol is None or eol > today:
            return str(cycle["latest"]["version"])
    return str(doc["cycles"][0]["latest"]["version"])


def aliases_for(doc: dict, version: str) -> list[str]:
    """The floating tags to move to this version when it is published.
    A new minor becomes the newest cycle and takes `X` and `latest`; a
    patch on an older cycle moves only its own `X.Y`."""
    cycle = cycle_of(version)
    major = cycle.split(".")[0]
    newest = doc["cycles"][0]["cycle"]
    if _cycle_tuple(cycle) >= _cycle_tuple(newest):
        return [cycle, major, "latest"]
    return [cycle]


def record(doc: dict, *, version: str, digest: str, date: dt.date, now: dt.datetime) -> dict:
    """What the publish job does after a signed push: add the version. Never
    edits dates that a human set, never removes anything."""
    if not _DIGEST_RE.match(digest):
        raise RegistryError(f"digest must be sha256:<64 hex>, got {digest!r}")
    version_tuple(version)
    cycle_name = cycle_of(version)
    doc = json.loads(json.dumps(doc))  # a copy; the caller decides whether to write
    cycles: list[dict] = doc["cycles"]
    existing = next((c for c in cycles if c.get("cycle") == cycle_name), None)
    entry = {"version": version, "date": date.isoformat(), "digest": digest}
    if existing is not None:
        if version_tuple(version) < version_tuple(str(existing["latest"]["version"])):
            raise RegistryError(f"{version} is older than {existing['latest']['version']} already recorded for cycle {cycle_name}")
        if version == existing["latest"]["version"] and existing["latest"]["digest"] != digest:
            raise RegistryError(f"{version} is already recorded with another digest — a version is one artifact")
        existing["latest"] = entry
    else:
        newest = cycles[0]
        if _cycle_tuple(cycle_name) < _cycle_tuple(str(newest["cycle"])):
            raise RegistryError(f"new cycle {cycle_name} is older than the newest {newest['cycle']}; a new cycle must be the newest")
        months = int(doc["support"]["maintenance_months"])
        # The previous newest closes on the day the new one opens (D-057):
        # security only from now, eol six months out, announced today.
        newest["state"] = "maintenance"
        newest["eoas"] = date.isoformat()
        newest["eol"] = _add_months(date, months).isoformat()
        newest["eol_announced"] = date.isoformat()
        newest["aliases"] = [str(newest["cycle"])]
        major = cycle_name.split(".")[0]
        cycles.insert(0, {
            "cycle": cycle_name, "state": "current", "release_date": date.isoformat(),
            "eoas": None, "eol": None, "eol_announced": None,
            "latest": entry, "aliases": [cycle_name, major, "latest"],
        })
    doc["updated_at"] = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return doc


def _add_months(day: dt.date, months: int) -> dt.date:
    month = day.month - 1 + months
    year = day.year + month // 12
    month = month % 12 + 1
    last = [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    return dt.date(year, month, min(day.day, last))


def _http_date(day: dt.date) -> str:
    return format_datetime(dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc), usegmt=True)


def _unix_at(day: dt.date) -> str:
    return "@" + str(int(dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc).timestamp()))


def verdict(doc: dict, engine_version: str, today: dt.date) -> dict:
    """The `version` block of a lease response (D-055)."""
    cycle = _cycle_for_verdict(doc, engine_version)
    latest = str(doc["cycles"][0]["latest"]["version"])
    in_cycle = str(cycle["latest"]["version"])
    announced = _date(cycle.get("eol_announced"), "eol_announced")
    eol = _date(cycle.get("eol"), "eol")
    return {
        "running_latest": engine_version == latest,
        "latest": latest,
        "latest_in_cycle": in_cycle,
        "min_supported": floor(doc, today),
        "deprecated_at": _unix_at(announced) if announced is not None and announced <= today else None,
        "sunset_at": _http_date(eol) if eol is not None else None,
        "notice": _notice_for(doc, engine_version),
    }


def check(doc: dict, engine_version: str, today: dt.date) -> dict | None:
    """The refusal, if one is due: the body of a 426, or None. Enforced only
    when the closing was announced in time (D-056); a late `eol` is served
    and reported by the caller, never obeyed."""
    cycle = _cycle_for_verdict(doc, engine_version)
    eol = _date(cycle.get("eol"), "eol")
    announced = _date(cycle.get("eol_announced"), "eol_announced")
    if eol is None or eol > today:
        return None
    notice_days = int(doc["support"]["eol_notice_days"])
    if announced is None or (eol - announced).days < notice_days or (today - announced).days < notice_days:
        return {"late": True, "cycle": str(cycle["cycle"]), "eol": eol.isoformat(),
                "eol_announced": announced.isoformat() if announced else None}
    minimum = floor(doc, today)
    latest = str(doc["cycles"][0]["latest"]["version"])
    return {
        "error": "unsupported_client",
        "detail": (f"engine {engine_version} (cycle {cycle['cycle']}) is past its end of life {eol.isoformat()}; "
                   f"the oldest supported version is {minimum}, the newest {latest}. "
                   f"Upgrade: pseudexctl upgrade --to {cycle_of(latest)}"),
        "min_supported": minimum,
        "latest": latest,
        "upgrade": f"pseudexctl upgrade --to {cycle_of(latest)}",
    }


# ── notices ──────────────────────────────────────────────────────────────────

_OPS = {">=": lambda a, b: a >= b, ">": lambda a, b: a > b, "<=": lambda a, b: a <= b,
        "<": lambda a, b: a < b, "==": lambda a, b: a == b}
_RANGE_TOKEN = re.compile(r"^(>=|<=|==|>|<)(\d+\.\d+\.\d+)$")


def _parse_range(expr: str) -> list[list[tuple[str, tuple[int, int, int]]]]:
    """`>=0.3.0 <0.3.17 || >=0.4.0 <0.4.2` → OR of AND-groups."""
    groups: list[list[tuple[str, tuple[int, int, int]]]] = []
    for part in expr.split("||"):
        terms: list[tuple[str, tuple[int, int, int]]] = []
        for token in part.split():
            match = _RANGE_TOKEN.match(token)
            if not match:
                raise RegistryError(f"bad range token {token!r} in {expr!r}")
            terms.append((match.group(1), version_tuple(match.group(2))))
        if not terms:
            raise RegistryError(f"empty range group in {expr!r}")
        groups.append(terms)
    return groups


def _matches(expr: str, version: str) -> bool:
    try:
        target = version_tuple(version)
    except RegistryError:
        return False
    return any(all(_OPS[op](target, bound) for op, bound in group) for group in _parse_range(expr))


def _notice_for(doc: dict, engine_version: str) -> dict | None:
    for notice in doc.get("notices", []):
        if _matches(str(notice["applies_to"]), engine_version):
            return {"id": notice["id"], "severity": notice["severity"],
                    "text": notice["text"], "url": notice["url"]}
    return None


# ── the server's live view ───────────────────────────────────────────────────

class Watch:
    """The registry as the licence server sees it: re-read when the file's
    mtime or inode changes (the host agent replaces it atomically), never
    fatal — a missing or broken file means «no version block, no floor», and
    that is logged once, not on every lease."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._doc: dict | None = None
        # A sentinel, not None: a missing file stats to None, and the first
        # call must still evaluate it (and record the error) rather than see
        # «unchanged since never».
        self._stamp: object = object()
        self._error: str | None = None
        self._lock = threading.Lock()

    def _stat(self) -> tuple[int, int, int] | None:
        try:
            info = os.stat(self.path)
        except OSError:
            return None
        return (info.st_ino, info.st_mtime_ns, info.st_size)

    def doc(self, today: dt.date) -> dict | None:
        if not self.path:
            return None
        stamp = self._stat()
        with self._lock:
            if stamp == self._stamp:
                return self._doc
            self._stamp = stamp
            if stamp is None:
                self._doc, self._error = None, "registry file is missing"
                return None
            try:
                doc = load(self.path)
                problems = validate(doc, previous=None, today=today)
            except (OSError, ValueError, RegistryError) as error:
                self._doc, self._error = None, f"registry unreadable: {error}"
                return None
            if problems:
                self._doc, self._error = None, "registry invalid: " + "; ".join(problems[:3])
                return None
            self._doc, self._error = doc, None
            return doc

    @property
    def error(self) -> str | None:
        return self._error


# ── CLI ──────────────────────────────────────────────────────────────────────

def _today(value: str | None) -> dt.date:
    return dt.date.fromisoformat(value) if value else dt.datetime.now(dt.timezone.utc).date()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="every way the file could lie")
    p_validate.add_argument("path")
    p_validate.add_argument("--previous", default=None, help="the file before this change (what a change may not do)")
    p_validate.add_argument("--today", default=None)

    p_record = sub.add_parser("record", help="add a published version (the publish job)")
    p_record.add_argument("path")
    p_record.add_argument("--version", required=True)
    p_record.add_argument("--digest", required=True)
    p_record.add_argument("--date", required=True)
    p_record.add_argument("--today", default=None)

    p_aliases = sub.add_parser("aliases", help="floating tags to move to this version")
    p_aliases.add_argument("path")
    p_aliases.add_argument("--version", required=True)

    p_verdict = sub.add_parser("verdict", help="the version block a container would receive")
    p_verdict.add_argument("path")
    p_verdict.add_argument("--engine-version", required=True)
    p_verdict.add_argument("--today", default=None)

    args = parser.parse_args(argv)
    today = _today(getattr(args, "today", None))
    doc = load(args.path)

    if args.command == "validate":
        previous = load(args.previous) if args.previous else None
        problems = validate(doc, previous=previous, today=today)
        for problem in problems:
            print(f"registry: {problem}", file=sys.stderr)
        print(f"{args.path}: {len(doc['cycles']) if isinstance(doc.get('cycles'), list) else 0} cycles, "
              f"{len(problems)} problems")
        return 1 if problems else 0
    if args.command == "record":
        problems = validate(doc, previous=None, today=today)
        if problems:
            print("refusing to record into an invalid registry: " + "; ".join(problems), file=sys.stderr)
            return 1
        updated = record(doc, version=args.version, digest=args.digest,
                         date=dt.date.fromisoformat(args.date), now=dt.datetime.now(dt.timezone.utc))
        problems = validate(updated, previous=doc, today=today)
        if problems:
            print("the recorded registry would be invalid: " + "; ".join(problems), file=sys.stderr)
            return 1
        dump(updated, args.path)
        print(f"recorded {args.version} ({args.digest[:19]}…) into cycle {cycle_of(args.version)}; "
              f"aliases {' '.join(aliases_for(updated, args.version))}")
        return 0
    if args.command == "aliases":
        print(" ".join(aliases_for(doc, args.version)))
        return 0
    if args.command == "verdict":
        block = verdict(doc, args.engine_version, today)
        refusal = check(doc, args.engine_version, today)
        print(json.dumps({"version": block, "refusal": refusal}, ensure_ascii=False, indent=2))
        return 0
    raise SystemExit(f"unknown command {args.command}")


if __name__ == "__main__":
    sys.exit(main())
