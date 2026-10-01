"""INDEPENDENT PAYLOAD CANARIES — construction-time manifest, exact matching.

    from bench.agentpii5 import payload_canaries as pc
    report = pc.scan(manifest, delivered)

WHY THIS EXISTS (S02). `leak` asks the detector's own spans whether the value
they covered reached the next party, so a value the detector never recognised is
invisible to it and a boundary that stopped one character short is invisible
too — the instrument and the layer under test share the premise. This module
asks a question that shares no premise with the engine: THE FIXTURE WROTE THE
LITERAL, THE FIXTURE NAMED THE BOUNDARY, so the ground truth is construction.

REDESIGNED IN ONE RESPECT THAT DECIDES EVERYTHING. Ground truth is now a
`CanaryManifest` built where the payload was built. It lists, per canary, the
BOUNDARY and the FULL ORIGINAL plus ONLY the fragments the fixture deliberately
planted. The scanner matches exactly those surfaces, boundary-aware; it infers
no prefix, cuts no substring, and never reads a value out of a saved corpus. A
leak exists iff a declared surface stands in the delivered bytes — full stop.

  detector        the type was never recognised at all;
  span            recognised, and the replaced range did not cover the literal;
  kv              the value's type comes from its KEY, and the key rule did not fire;
  result-payload  detector, span and key all fine — the result/error text path lost it;
  oracle          every layer says covered, yet the literal is in the payload.

Those four are CLASSIFICATION AND NOTHING MORE. Detector/span/KV/result evidence
may label a leak the manifest already found; it may never decide whether one
exists. `scan` decides; `classify` decorates.

A RUN WITHOUT A MANIFEST IS NOT_MEASURED. A saved run must carry a versioned
`canary_manifest.json`; with none, `check_run` says NOT_MEASURED rather than
synthesising provenance or neighbours out of spans — the synthesis was the
defect this redesign removes.
"""
from __future__ import annotations

import json
import pathlib
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace

# The boundaries a payload crosses, named as the row names them. `tool_result`
# and `tool_error` are separate entries on purpose: S01 was an error payload.
BOUNDARIES: tuple[str, ...] = (
    "model_input", "tool_args", "tool_result", "tool_error", "final_answer")

# The boundaries the FIXTURE writes, plus the composed model-bound payload the
# real harness can show and a hand-written fixture cannot: the whole transcript
# the provider is sent, which is what the model actually reads. It is a boundary
# of its own because the per-message scan proves each message was masked and
# says nothing about the composition that carries them.
CAPTURE_BOUNDARIES: tuple[str, ...] = BOUNDARIES + ("model_request",)

STATUS_MEASURED: str = "MEASURED"
STATUS_NOT_MEASURED: str = "NOT_MEASURED"

# The classes a miss can carry. `unclassified` is the honest label for a leak
# found by the manifest with no evidence supplied to explain it; it is a real
# answer, never a silent drop.
UNCLASSIFIED: str = "unclassified"
MISS_CLASSES: tuple[str, ...] = ("detector", "span", "kv", "result-payload", "oracle")

# A surface is either the whole planted value or a fragment the fixture wrote on
# purpose. There is no third kind: the scanner never derives one.
SURFACE_FULL: str = "full"
SURFACE_FRAGMENT: str = "fragment"

# Bump when the manifest wire shape changes; a reader refuses a version it does
# not know rather than guessing at the fields.
MANIFEST_VERSION: int = 1
MANIFEST_ARTIFACT: str = "canary_manifest.json"

# THE DELIVERED BYTES ARE THEIR OWN VERSIONED ARTIFACT (S02 capture). The
# manifest says what must not be there; this file says what was there. They are
# written at DIFFERENT moments — the manifest at case construction, the bytes at
# capture time — so one file for both would have to be rewritten per triple, and
# a reader that found a stale half would decide leaks from bytes another run
# delivered.
#
# `NPY_CANARY_CAPTURE=1` disables the whole capture: a battery that is not the
# canary instrument pays no artifact size at all, and the run then reports
# NOT_MEASURED rather than silently reading somebody else's bytes.
CAPTURE_VERSION: int = 1
CAPTURE_ARTIFACT: str = "<run>.canary.jsonl"
CAPTURE_SUFFIX: str = ".canary.jsonl"
CAPTURE_KILL_SWITCH: str = "NPY_CANARY_CAPTURE"

# THE SIZE, STATED AS A BOUNDARY AND NOT AS A HOPE. A capture row holds the
# corpus's own text, so an unreadable or hostile file is a real shape (not a
# hypothetical one) and it must be refused by ARITHMETIC rather than by running
# out of memory. The bound that decides a row is broken is the PAYLOAD bound,
# not the row byte count: a chatty but valid run (380 payloads of ≤36.6 KB each)
# legitimately exceeds the old 4 MiB row ceiling and was wrongly refused whole.
# The row bound is a DERIVED outer ceiling; a single payload over the payload
# bound is the hostile shape. A size-bound violation is SKIPPED (named, counted),
# never a whole-run abort; a MALFORMED row (bad UTF-8/JSON/schema) still raises,
# because a corrupt archive cannot produce a trustworthy denominator.
CAPTURE_MAX_ROW_BYTES: int = 8 * 1024 * 1024
CAPTURE_MAX_RUN_BYTES: int = 256 * 1024 * 1024
CAPTURE_MAX_PAYLOAD_UTF8_BYTES: int = 1 * 1024 * 1024
CAPTURE_MAX_PAYLOADS: int = 4096

# The contexts a planted value can sit in. They select the last class, not the
# first: a result-payload leak whose type was never recognised is still a
# `detector` miss, because fixing the payload path would not have saved it.
_RESULT_CONTEXTS: frozenset[str] = frozenset(("result", "error"))

# The locus kinds the record distinguishes. Only a value that STOOD IN A MESSAGE
# has a declared range, so only there is «did the replaced span cover it» a
# question; a seed value came from a tool result and has no message offset.
MESSAGE_LOCUS: str = "message"
SEED_LOCUS: str = "seed"


# --- the manifest, written where the payload was built --------------------------------

@dataclass(frozen=True)
class PlantedSurface:
    """One literal the fixture DELIBERATELY wrote into this payload.

    `kind` is `SURFACE_FULL` for the whole original and `SURFACE_FRAGMENT` for a
    cut the fixture planted on purpose. Nothing else is ever scanned."""

    text: str
    kind: str


@dataclass(frozen=True)
class CanarySpec:
    """One canary at ONE boundary: what must not be there, and where it stood."""

    id: str
    pii_type: str
    boundary: str
    surfaces: tuple[PlantedSurface, ...]
    substitute: str = ""
    context: str = "message"


@dataclass(frozen=True)
class Neighbour:
    """An ordinary literal the fixture wrote that must SURVIVE the masking.

    An explicit construction-time literal, never a token picked out of saved
    payload text: an instrument whose over-masking axis is derived from whatever
    text happens to be on disk measures the derivation, not the gateway."""

    boundary: str
    text: str


@dataclass(frozen=True)
class CanaryManifest:
    """Every forbidden surface of one run, listed by construction.

    `version` is checked on read; `source` names who built it so a report can
    never present a synthesised manifest as a constructed one."""

    canaries: tuple[CanarySpec, ...]
    neighbours: tuple[Neighbour, ...] = ()
    salt: str = ""
    source: str = "construction"
    version: int = MANIFEST_VERSION

    def boundaries(self) -> tuple[str, ...]:
        out: list[str] = []
        for spec in self.canaries:
            if spec.boundary not in out:
                out.append(spec.boundary)
        return tuple(out)


def manifest_to_json(manifest: CanaryManifest) -> dict[str, object]:
    """The versioned artifact a saved run must carry."""
    return {
        "version": manifest.version,
        "manifest": {
            "salt": manifest.salt,
            "source": manifest.source,
            "canaries": [
                {"id": spec.id, "pii_type": spec.pii_type, "boundary": spec.boundary,
                 "substitute": spec.substitute, "context": spec.context,
                 "surfaces": [{"text": one.text, "kind": one.kind} for one in spec.surfaces]}
                for spec in manifest.canaries],
            "neighbours": [{"boundary": one.boundary, "text": one.text}
                           for one in manifest.neighbours],
        },
    }


def manifest_from_json(raw: Mapping[str, object]) -> CanaryManifest | None:
    """Read a versioned manifest artifact, or refuse it.

    A version this reader does not know is REFUSED rather than read leniently:
    a manifest read with the wrong field meanings would decide leaks from a
    surface the fixture never planted."""
    if int(raw.get("version", -1)) != MANIFEST_VERSION:
        return None
    body = raw.get("manifest")
    if not isinstance(body, Mapping):
        return None
    canaries = tuple(
        CanarySpec(
            id=str(one["id"]), pii_type=str(one["pii_type"]),
            boundary=str(one["boundary"]),
            surfaces=tuple(PlantedSurface(str(s["text"]), str(s["kind"]))
                           for s in one.get("surfaces", [])),
            substitute=str(one.get("substitute", "")), context=str(one.get("context", "")))
        for one in body.get("canaries", []) if isinstance(one, Mapping))
    neighbours = tuple(Neighbour(str(one["boundary"]), str(one["text"]))
                       for one in body.get("neighbours", []) if isinstance(one, Mapping))
    return CanaryManifest(canaries=canaries, neighbours=neighbours,
                          salt=str(body.get("salt", "")), source=str(body.get("source", "artifact")))


# --- the scan: exact, boundary-aware, manifest-only -----------------------------------

def _digits_of(text: str) -> str:
    return "".join(char for char in text if char.isdigit())


def _numeric(literal: str) -> bool:
    return bool(_digits_of(literal)) and not any(char.isalpha() for char in literal)


def _flat(text: str) -> str:
    """Case and ё→е, both of which a Russian value and its copy share."""
    return text.replace("Ё", "Е").replace("ё", "е").lower()


# A number TOKEN: a digit or a leading sign followed by digits and the
# separators a notation uses. «+7 916 123-45-67» is ONE token, and its digit run
# is compared for EQUALITY — so a longer number that merely starts with the
# value's digits is another number, not a truncated one.
_NUMBER_TOKEN = re.compile(r"[+\d][\d\s\-()./]*")


def _number_runs(text: str) -> tuple[str, ...]:
    return tuple(run for run in (_digits_of(one) for one in _NUMBER_TOKEN.findall(text)) if run)


def surface_in(text: str, surface: str) -> bool:
    """Does the DECLARED surface stand in `text`, at a real boundary?

    NUMERIC: the surface's digit run must EQUAL a whole number token of the
    text. Equality is what makes «the value's digits followed by three more» a
    different number and an undeclared cut a non-match.

    TEXT: the surface must be a whole word (or whole word phrase) of the text,
    so «Канарей» inside «Канарейкин» is not a match and neither is a longer word
    that starts with the surface.
    """
    if not text or not surface:
        return False
    if _numeric(surface):
        want = _digits_of(surface)
        return any(run == want for run in _number_runs(text))
    phrase = r"\s+".join(re.escape(part) for part in _flat(surface).split())
    return re.search(r"(?<!\w)" + phrase + r"(?!\w)", _flat(text)) is not None


def declared_surface_hit(text: str, spec: CanarySpec) -> PlantedSurface | None:
    """The FIRST declared surface of `spec` present in `text`, or None.

    Order is the manifest's, so a spec that declares the full value before a
    fragment reports the full one — the stronger finding for the same class."""
    for surface in spec.surfaces:
        if surface_in(text, surface.text):
            return surface
    return None


@dataclass(frozen=True)
class CapturedPayload:
    """One payload as the next party received it, plus the pre-mask bytes.

    `text` is what was delivered and is ALL the scanner reads. `real_text` is
    kept only so a mutant can put the real value back without the mutant having
    to know the case."""

    name: str
    text: str
    real_text: str = ""


@dataclass(frozen=True)
class Leak:
    canary_id: str
    boundary: str
    pii_type: str
    surface: str
    surface_kind: str
    miss_class: str
    why: str


@dataclass(frozen=True)
class CanaryReport:
    status: str
    hidden: tuple[str, ...]
    leaks: tuple[Leak, ...]
    neighbour_damage: tuple[str, ...]
    unclassified: tuple[str, ...]
    boundaries: tuple[str, ...]
    coverage_known: bool
    capture_rows: int
    intervention_rows: int
    selected_rows: int
    unreached: tuple[str, ...] = ()
    reason: str = ""

    @property
    def ok(self) -> bool:
        return (self.status == STATUS_MEASURED and not self.leaks
                and not self.neighbour_damage and not self.unclassified
                and not self.unreached)

    def counts(self) -> dict[str, int]:
        """Leaks per class, so a report can print WHY the coverage is short."""
        out = {name: 0 for name in MISS_CLASSES}
        out[UNCLASSIFIED] = 0
        for leak in self.leaks:
            out[leak.miss_class] = out.get(leak.miss_class, 0) + 1
        return out

    def by_boundary(self) -> dict[str, dict[str, int]]:
        """Per boundary: how many canaries were hidden and how many leaked.

        PRINTED PER BOUNDARY AND NOT SUMMED. One number over five paths hides
        which path leaked, and S01 was exactly that: the corpus was clean on the
        input and the leak lived in an ERROR payload nobody counted apart. A row
        is present for every boundary the manifest names, even one this run
        never reached — a missing row would read as a clean one."""
        out = {name: {"hidden": 0, "leaked": 0} for name in self.boundaries}
        for entry in self.hidden:
            name = entry.split(":", 1)[0]
            out.setdefault(name, {"hidden": 0, "leaked": 0})["hidden"] += 1
        for leak in self.leaks:
            out.setdefault(leak.boundary, {"hidden": 0, "leaked": 0})["leaked"] += 1
        return out


def not_measured(reason: str) -> CanaryReport:
    """A run that cannot be measured, said in the same type as a measured one.

    `status` is what a caller reads; `ok` is False because «not measured» is not
    «clean», and the two readings are exactly what this redesign exists to keep
    apart."""
    return CanaryReport(status=STATUS_NOT_MEASURED, hidden=(), leaks=(),
                        neighbour_damage=(), unclassified=(), boundaries=(),
                        coverage_known=False, capture_rows=0,
                        intervention_rows=0, selected_rows=0,
                        reason=reason)


# --- the delivered bytes: a versioned artifact, written where they were delivered -------

class CaptureError(ValueError):
    """A capture artifact this reader refuses. Never a crash: `check_run` turns
    it into NOT_MEASURED with the sentence intact."""


@dataclass(frozen=True)
class RunCapture:
    """One (case, repeat) at the arm the model bound: its manifest and its bytes.

    `delivered` is the EXACT sequence `GatewayV5` handed the boundaries, in the
    order it handed them, with the composed `model_request` appended as its own
    boundary. Nothing here is reconstructed: what a scan reads is what the run
    wrote at the moment of delivery, which is the whole point of the artifact."""

    case_id: str
    repeat: int
    arm: str
    manifest: CanaryManifest
    delivered: tuple[CapturedPayload, ...]


def capture_name(run_id: str) -> str:
    """The artifact's file name for a run id — one id, one file.

    `run_id` becomes a path component, so the ids that would ESCAPE the run
    directory are refused here: an id is ours (`uuid4` in the harness), and a
    reader/writer pair that accepts `../` for one is a way to write the corpus
    into another run's directory and read it back as that run's bytes."""
    if not run_id or run_id != pathlib.PurePath(run_id).name or run_id in (".", ".."):
        raise CaptureError(f"capture: {run_id!r} is not a usable run id")
    return CAPTURE_ARTIFACT.replace("<run>", run_id)


def capture_row(run: RunCapture) -> dict[str, object]:
    """One JSON object, in the versioned shape the reader knows.

    The manifest travels INSIDE the capture so a single row is self-contained:
    a reader that finds the row can measure it without a second file that could
    belong to another run."""
    return {
        "version": CAPTURE_VERSION,
        "case_id": run.case_id,
        "repeat": int(run.repeat),
        "arm": run.arm,
        "capture": {
            "manifest": manifest_to_json(run.manifest)["manifest"],
            "payloads": [{"name": one.name, "text": one.text, "real_text": one.real_text}
                         for one in run.delivered],
        },
    }


def capture_from_json(raw: Mapping[str, object]) -> RunCapture:
    """Read one capture row, or raise `CaptureError` naming the field.

    REFUSED, NEVER COERCED, for the four things that would turn a reader into a
    liar: a version this reader does not know, a body that is not an object, a
    payload naming a boundary outside `CAPTURE_BOUNDARIES` (a row no consumer has
    a column for), and a payload whose text is not a string."""
    if int(raw.get("version", -1)) != CAPTURE_VERSION:
        raise CaptureError(f"capture: version {raw.get('version')!r}, this reader knows only "
                           f"{CAPTURE_VERSION}")
    case_id = raw.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        raise CaptureError("capture: case_id must be a non-empty string")
    repeat = raw.get("repeat")
    if not isinstance(repeat, int) or isinstance(repeat, bool):
        raise CaptureError(f"capture: repeat must be an integer, found {repeat!r}")
    body = raw.get("capture")
    if not isinstance(body, Mapping):
        raise CaptureError("capture: no capture object in the row")
    manifest = manifest_from_json({"version": MANIFEST_VERSION, "manifest": body.get("manifest")})
    if manifest is None:
        raise CaptureError("capture: the row carries no readable manifest")
    payloads: list[CapturedPayload] = []
    for one in body.get("payloads", []):
        if not isinstance(one, Mapping):
            raise CaptureError(f"capture: payload {one!r} is not an object")
        name = one.get("name")
        if name not in CAPTURE_BOUNDARIES:
            raise CaptureError(f"capture: payload names {name!r}, which is not one of "
                               f"{CAPTURE_BOUNDARIES}")
        text, real_text = one.get("text"), one.get("real_text", "")
        if not isinstance(text, str) or not isinstance(real_text, str):
            raise CaptureError(f"capture: payload {name!r} carries non-string bytes")
        payloads.append(CapturedPayload(str(name), text, real_text))
    return RunCapture(case_id=case_id, repeat=int(repeat), arm=str(raw.get("arm", "")),
                      manifest=manifest, delivered=tuple(payloads))


def append_capture(run_dir: pathlib.Path, run_id: str, capture: RunCapture) -> pathlib.Path:
    """Append ONE capture row to the run's artifact, flushed to its own line.

    Append and not rewrite for v4's reason: the row is on disk before the next
    triple starts. `ensure_ascii=False` because every byte here is the run's own
    Russian text and a JSON-escaped artifact is not auditable against the corpus."""
    path = run_dir / capture_name(run_id)
    with path.open("a", encoding="utf-8") as sink:
        sink.write(json.dumps(capture_row(capture), ensure_ascii=False) + "\n")
    return path


def capture_paths(run_dir: pathlib.Path) -> tuple[pathlib.Path, ...]:
    """Every capture artifact in a run directory, in name order."""
    return tuple(sorted(run_dir.glob("*" + CAPTURE_SUFFIX)))


def read_captures_detailed(run_dir: pathlib.Path) -> tuple[tuple[RunCapture, ...], tuple[str, ...]]:
    """Read every capture row plus the named rows skipped for a SIZE bound.

    A row over a hard size bound (row ceiling, payload byte, payload count) is
    SKIPPED with a named, counted record and the remaining rows are still read —
    never a whole-run abort. A MALFORMED row (bad UTF-8, bad JSON, bad schema,
    duplicate key) still raises `CaptureError`: a corrupt archive cannot produce
    a trustworthy denominator. The run budget is a whole-run refusal, not a skip.
    """
    out: list[RunCapture] = []
    skipped: list[str] = []
    total = 0
    seen: dict[tuple[str, int], str] = {}
    for path in capture_paths(run_dir):
        try:
            size = path.stat().st_size
        except OSError as error:
            raise CaptureError(f"{path.name}: could not be sized ({type(error).__name__})") from error
        total += size
        if total > CAPTURE_MAX_RUN_BYTES:
            raise CaptureError(f"the run's capture artifacts are over the "
                               f"{CAPTURE_MAX_RUN_BYTES} byte bound")
        try:
            with path.open("rb") as source:
                number = 0
                while True:
                    raw = source.readline(CAPTURE_MAX_ROW_BYTES + 1)
                    if not raw:
                        break
                    number += 1
                    if len(raw) > CAPTURE_MAX_ROW_BYTES:
                        skipped.append(f"{path.name}:{number}: row over the "
                                       f"{CAPTURE_MAX_ROW_BYTES} byte bound")
                        continue
                    try:
                        line = raw.decode("utf-8")
                    except UnicodeDecodeError as error:
                        raise CaptureError(f"{path.name}:{number}: invalid UTF-8") from error
                    if not line.strip():
                        continue
                    try:
                        parsed = json.loads(line)
                    except json.JSONDecodeError as error:
                        raise CaptureError(f"{path.name}:{number}: not JSON ({error})") from error
                    if not isinstance(parsed, Mapping):
                        raise CaptureError(f"{path.name}:{number}: expected an object, found "
                                           f"{type(parsed).__name__}")
                    try:
                        captured = capture_from_json(parsed)
                    except CaptureError as broken:
                        raise CaptureError(f"{path.name}:{number}: {broken}") from broken
                    if len(captured.delivered) > CAPTURE_MAX_PAYLOADS:
                        skipped.append(f"{path.name}:{number}: {len(captured.delivered)} payloads "
                                       f"over the {CAPTURE_MAX_PAYLOADS} payload bound")
                        continue
                    oversized = next((one.name for one in captured.delivered
                                      if len(one.text.encode("utf-8")) > CAPTURE_MAX_PAYLOAD_UTF8_BYTES
                                      or len(one.real_text.encode("utf-8")) > CAPTURE_MAX_PAYLOAD_UTF8_BYTES),
                                     None)
                    if oversized is not None:
                        skipped.append(f"{path.name}:{number}: payload {oversized!r} over the "
                                       f"{CAPTURE_MAX_PAYLOAD_UTF8_BYTES} byte bound")
                        continue
                    key = (captured.case_id, captured.repeat)
                    if key in seen:
                        raise CaptureError(f"{path.name}:{number}: duplicate capture for "
                                           f"{key!r}; first row at {seen[key]}")
                    seen[key] = f"{path.name}:{number}"
                    out.append(captured)
        except OSError as error:
            raise CaptureError(f"{path.name}: could not be read "
                               f"({type(error).__name__}: {error})") from error
    return tuple(out), tuple(skipped)


def read_captures(run_dir: pathlib.Path) -> tuple[RunCapture, ...]:
    """Every capture row this run holds, or a `CaptureError` naming a malformed
    shape. Size-bound-violating rows are SKIPPED, not raised — callers that need
    the skip record use `read_captures_detailed`."""
    return read_captures_detailed(run_dir)[0]

def merge_reports(reports: Sequence[CanaryReport]) -> CanaryReport:
    """One report over several captures — summed by boundary, leaks preserved.

    A directory holds every (case, repeat) of a battery, so the reader has one
    report per capture and the consumer wants one table. `hidden` carries one
    entry PER HIDDEN OBSERVATION with the capture's case and repeat appended:
    `by_boundary()` counts them by prefix, so the merged table is the sum of the
    part tables and not the size of a deduplicated set — two captures of one case
    hid two canaries, and a merged row that read `1` would disagree with the
    table it replaced. A leak keeps its canary id, which already names its case.
    `unreached` is the INTERSECTION: a boundary the whole battery never delivered
    is unreached; one some capture reached is reached."""
    live = tuple(one for one in reports if one.status == STATUS_MEASURED)
    if not live:
        return reports[0] if reports else not_measured("no capture was measured")
    hidden: list[str] = []
    leaks: list[Leak] = []
    damage: list[str] = []
    unreached: list[str] = []
    for one in live:
        hidden.extend(one.hidden)
        leaks.extend(one.leaks)
        damage.extend(one.neighbour_damage)
        unreached.extend(one.unreached)
    shared = set.intersection(*(set(one.unreached) for one in live)) if live else set()
    return CanaryReport(
        status=STATUS_MEASURED, hidden=tuple(hidden), leaks=tuple(leaks),
        neighbour_damage=tuple(dict.fromkeys(damage)),
        unclassified=tuple(one.canary_id for one in leaks
                           if one.miss_class not in MISS_CLASSES),
        boundaries=tuple(dict.fromkeys(one for report in live for one in report.boundaries)),
        coverage_known=False, capture_rows=0, intervention_rows=0,
        selected_rows=0,
        unreached=tuple(one for one in dict.fromkeys(unreached) if one in shared),
        reason=live[0].reason)


def scan_captures(captures: Sequence[RunCapture],
                  fallback: CanaryManifest | None = None,
                  evidence: ProvenanceEvidence | None = None) -> tuple[CanaryReport, ...]:
    """One report per capture, each against ITS OWN manifest.

    THE MANIFEST PAIRS WITH THE BYTES IT WAS CONSTRUCTED FOR. A directory-level
    `canary_manifest.json` is used only for a capture that carries none (an older
    writer), and never to override the row's own: two cases in one battery have
    different manifests, and one of them applied to both would report the other's
    declared surfaces as leaks."""
    return tuple(scan(run.manifest if run.manifest.canaries else (fallback or run.manifest),
                      run.delivered, evidence) for run in captures)


def scan(manifest: CanaryManifest,
         delivered: Sequence[CapturedPayload],
         evidence: ProvenanceEvidence | None = None) -> CanaryReport:
    """Every declared surface against the delivered bytes — and nothing else.

    THE ONLY QUESTION ASKED IS `surface_in(delivered_bytes, declared_surface)`.
    Evidence never widens it: a leak whose class the evidence cannot explain is
    reported with `UNCLASSIFIED` and never dropped, and a leak the evidence
    would have predicted but the bytes do not contain is NOT reported, because
    the bytes are the truth.

    AN EMPTY HERD IS NOT A CLEAN RUN. A manifest that declares no canary has no
    denominator, so `ok=True` about it would be the green verdict on zero
    evidence — the reading `check_run` refuses for a saved run, refused here too
    so no entry point can turn «planted nothing» into «no leaks»."""
    if not manifest.canaries:
        return not_measured(
            "the manifest declares 0 canaries: with no denominator there is nothing to "
            "measure, and «no leaks» about an empty herd is not a fact")
    seen: dict[str, list[str]] = {}
    for one in delivered:
        seen.setdefault(one.name, []).append(one.text)
    leaks: list[Leak] = []
    hidden: list[str] = []
    damage: list[str] = []
    unclassified: list[str] = []
    unreached: list[str] = []
    for spec in manifest.canaries:
        texts = seen.get(spec.boundary)
        if texts is None:
            unreached.append(spec.boundary)
            continue
        hit = next((surface for surface in spec.surfaces
                    if any(surface_in(text, surface.text) for text in texts)), None)
        if hit is None:
            hidden.append(f"{spec.boundary}:{spec.id}")
            continue
        miss_class = classify(evidence, spec) if evidence is not None else UNCLASSIFIED
        leaks.append(Leak(canary_id=spec.id, boundary=spec.boundary, pii_type=spec.pii_type,
                          surface=hit.text, surface_kind=hit.kind, miss_class=miss_class,
                          why=_why(miss_class, hit)))
        if miss_class not in MISS_CLASSES:
            unclassified.append(spec.id)
    for neighbour in manifest.neighbours:
        texts = seen.get(neighbour.boundary)
        if texts is not None and not any(surface_in(text, neighbour.text) for text in texts):
            damage.append(f"{neighbour.boundary}: {neighbour.text!r}")
    return CanaryReport(
        status=STATUS_MEASURED, hidden=tuple(hidden), leaks=tuple(leaks),
        neighbour_damage=tuple(damage), unclassified=tuple(unclassified),
        boundaries=manifest.boundaries(),
        coverage_known=False, capture_rows=0, intervention_rows=0,
        selected_rows=0,
        unreached=tuple(dict.fromkeys(unreached)))


# --- classification: decoration over an already-detected leak -------------------------

@dataclass(frozen=True)
class ProvenanceEvidence:
    """What a run's OWN record says, used to LABEL a leak and nothing more.

    `substitutes` maps an item id to the substitute minted for it; `span_missed`
    names message values whose declared range no replaced span covered;
    `key_typed` names values whose type came from the key that carried them."""

    substitutes: Mapping[str, str] = field(default_factory=dict)
    span_missed: frozenset[str] = frozenset()
    key_typed: frozenset[str] = frozenset()


def _locus_kind(item: object) -> str:
    return str(getattr(getattr(item, "where", None), "kind", "") or "")


def evidence_from_spans(items: Iterable[object], masked_spans: Mapping[int, object],
                        substitutes: Mapping[str, str] | None = None) -> ProvenanceEvidence:
    """Read the record's evidence once, for the classifier only.

    Three sources: a message value is `span_missed` when its DECLARED range is
    covered by no replaced span of that message; a value whose declared locus is
    neither a message nor a seed is `key_typed`; `substitutes` is passed through
    from the caller that read the mentions."""
    span_missed: set[str] = set()
    key_typed: set[str] = set()
    for item in items:
        item_id = str(getattr(item, "id", ""))
        kind = _locus_kind(item)
        if kind == MESSAGE_LOCUS:
            where = getattr(item, "where", None)
            msg = int(getattr(where, "msg", -1))
            spans = masked_spans.get(msg, ()) if masked_spans else ()
            start = int(getattr(where, "start", 0))
            end = int(getattr(where, "end", 0))
            if not any(int(one[0]) <= start and end <= int(one[1]) for one in spans):
                span_missed.add(item_id)
        elif kind not in (SEED_LOCUS, ""):
            key_typed.add(item_id)
    return ProvenanceEvidence(substitutes=dict(substitutes or {}),
                              span_missed=frozenset(span_missed),
                              key_typed=frozenset(key_typed))


def classify(evidence: ProvenanceEvidence, spec: CanarySpec) -> str:
    """The innermost layer that can explain an ALREADY-DETECTED leak."""
    if spec.id not in evidence.substitutes:
        return "detector"
    if spec.id in evidence.span_missed:
        return "span"
    if spec.id in evidence.key_typed:
        return "kv"
    if spec.context in _RESULT_CONTEXTS:
        return "result-payload"
    return "oracle"


def _why(miss_class: str, surface: PlantedSurface) -> str:
    partial = " — a planted fragment, not the whole value" if surface.kind == SURFACE_FRAGMENT else ""
    return {
        "detector": "the type was never recognised, so no replacement was attempted",
        "span": "the replaced range did not cover the literal",
        "kv": "the value is typed by its key and the key rule did not fire",
        "result-payload": "the result/error payload path left the value standing",
        "oracle": "every layer reports the value replaced, yet it is in the payload",
        "unclassified": "the manifest found the declared surface; no evidence was supplied to classify it",
    }[miss_class] + partial


# --- the constructed fixture: the scanner's own red set -------------------------------

@dataclass(frozen=True)
class CanaryFixture:
    """A manifest and the payloads a CORRECT gateway delivers for it.

    Both ends are construction: the manifest names the forbidden surfaces, the
    delivery names what a right gateway puts in their place. A test mutates the
    delivery; the scan never learns the mutation except through the bytes."""

    salt: str
    manifest: CanaryManifest
    delivered: tuple[CapturedPayload, ...]
    # The literal a `make_number_fixture` built, so a test can cut it without
    # re-deriving the fixture's own arithmetic.
    full_literal: str = ""

    def boundary(self, name: str) -> CapturedPayload:
        return next(one for one in self.delivered if one.name == name)


def _seed(salt: str) -> int:
    return (sum(ord(char) for char in salt) if salt else 17) % 89


def make_canary_fixture(salt: str = "") -> CanaryFixture:
    """Five boundaries, one canary herd, explicit neighbours — all constructed."""
    seed = _seed(salt)
    suffix = salt.replace(" ", "-")
    phone = f"+7 9{16 + seed % 3} {100 + seed:03d}-{10 + seed % 89:02d}-{20 + seed % 79:02d}"
    fake_phone = f"+7 9{17 + seed % 3} {400 + seed:03d}-{50 + seed % 49:02d}-{60 + seed % 39:02d}"
    name = f"Канарейкин{suffix} Пётр"
    fake_name = f"Жаворонков{suffix} Илья"
    street = f"Канареечная{suffix}"
    fake_street = f"Соловьиная{suffix}"
    house = str(7 + seed % 40)
    order = str(4821 + seed)
    address = f"ул. {street}, д. {house}"
    fake_address = f"ул. {fake_street}, д. {house}"

    number, person, place = "PHONE", "NAME", "LOC"
    full = lambda text: (PlantedSurface(text, SURFACE_FULL),)  # noqa: E731

    # Per boundary: the pre-mask bytes and EVERY planted literal with the
    # substitute a right gateway puts in its place. Applying them all is what
    # makes the delivered payload the correct one — masking only the canary a
    # test looks at is how a fixture launders its own leak.
    plan: dict[str, tuple[str, tuple[tuple[str, str], ...], tuple[CanarySpec, ...]]] = {
        "model_input": (
            f"Прошу перезвонить {phone} и подтвердить заказ {order}.",
            ((phone, fake_phone),),
            (CanarySpec("in-phone", number, "model_input", full(phone), fake_phone, "message"),)),
        "tool_args": (
            f'{{"client": "{name}", "contact": {phone}, "order": {order}}}',
            ((name, fake_name), (phone, fake_phone)),
            (CanarySpec("arg-name", person, "tool_args", full(name), fake_name, "argument"),
             CanarySpec("arg-phone", number, "tool_args", full(phone), fake_phone, "argument"))),
        "tool_result": (
            f"Клиент: {name}\nАдрес: {address}\nСтатус: доставлен {order}\n",
            ((name, fake_name), (address, fake_address)),
            (CanarySpec("res-name", person, "tool_result", full(name), fake_name, "result"),
             CanarySpec("res-address", place, "tool_result", full(address), fake_address, "result"))),
        "tool_error": (
            f"Ошибка: номер {phone} не найден; запрос {order} отклонён",
            ((phone, fake_phone),),
            (CanarySpec("err-phone", number, "tool_error", full(phone), fake_phone, "error"),)),
        "final_answer": (
            f"Готово: {name}, {address}.",
            ((name, fake_name), (address, fake_address)),
            (CanarySpec("ans-name", person, "final_answer", full(name), fake_name, "answer"),
             CanarySpec("ans-address", place, "final_answer", full(address), fake_address, "answer"))),
    }
    canaries: list[CanarySpec] = []
    delivered: list[CapturedPayload] = []
    for boundary, (real_text, swaps, specs) in plan.items():
        masked_text = real_text
        for literal, substitute in swaps:
            masked_text = masked_text.replace(literal, substitute)
        canaries.extend(specs)
        delivered.append(CapturedPayload(name=boundary, text=masked_text, real_text=real_text))
    neighbours = (
        Neighbour("model_input", f"подтвердить заказ {order}"),
        Neighbour("tool_args", f'"order": {order}'),
        Neighbour("tool_result", f"Статус: доставлен {order}"),
        Neighbour("tool_error", "не найден"),
        Neighbour("final_answer", "Готово"),
    )
    return CanaryFixture(salt=salt,
                         manifest=CanaryManifest(canaries=tuple(canaries), neighbours=neighbours,
                                                 salt=salt),
                         delivered=tuple(delivered))


def make_number_fixture(delivered_number: str, fragments: tuple[str, ...] = (),
                        salt: str = "") -> CanaryFixture:
    """One `model_input` number boundary whose delivered bytes and declared
    FRAGMENTS a test chooses — the seam the cut/prefix/longer-number cases use.

    The manifest always declares the full literal it built, plus exactly the
    fragments passed here. Nothing else is ever scanned, which is what makes an
    undeclared prefix and a longer number negatives BY CONSTRUCTION."""
    seed = _seed(salt)
    order = str(4821 + seed)
    phone = f"+7 9{16 + seed % 3} {100 + seed:03d}-{10 + seed % 89:02d}-{20 + seed % 79:02d}"
    real_text = f"Прошу перезвонить {phone} и подтвердить заказ {order}."
    delivered_text = f"Прошу перезвонить {delivered_number} и подтвердить заказ {order}."
    surfaces = (PlantedSurface(phone, SURFACE_FULL),) + tuple(
        PlantedSurface(one, SURFACE_FRAGMENT) for one in fragments)
    spec_ = CanarySpec("num", "PHONE", "model_input", surfaces, "", "message")
    manifest = CanaryManifest(canaries=(spec_,),
                              neighbours=(Neighbour("model_input", f"подтвердить заказ {order}"),),
                              salt=salt)
    return CanaryFixture(salt=salt, manifest=manifest, full_literal=phone,
                         delivered=(CapturedPayload("model_input", delivered_text, real_text),))


def mutant_capture(captured: Sequence[CapturedPayload], name: str) -> tuple[CapturedPayload, ...]:
    """The leaky mutant where each payload of `name` DELIVERS ITS OWN PRE-MASK
    BYTES — the real value put back where the mask should have been.

    Per payload and not one shared string: a boundary can be delivered several
    times (one user message each, plus the system prompt), and replacing them
    all with the first one's text would scan the wrong payload."""
    return tuple(replace(one, text=one.real_text) if one.name == name else one
                 for one in captured)


def replace_delivery(fixture: CanaryFixture, name: str, text: str) -> CanaryFixture:
    """The fixture with one boundary's DELIVERED bytes replaced."""
    return replace(fixture, delivered=tuple(
        replace(one, text=text) if one.name == name else one for one in fixture.delivered))


# --- the real run: a saved run must CARRY its manifest --------------------------------

def read_manifest(run_dir: pathlib.Path) -> CanaryManifest | None:
    """The versioned sidecar manifest of a saved run, or None when it is absent.

    THE CAPTURE ARTIFACT IS THE ONE REQUIRED ARTIFACT (S02 capture): it carries
    the manifest and the delivered bytes together, and `check_run` measures from
    it alone. This reader remains for the sidecar file the report-side writer
    plants, and for a caller that wants the manifest without the bytes."""
    manifest, problem = load_manifest(run_dir)
    if problem:
        return None
    return manifest


def _capture_problem(captures: Sequence[RunCapture]) -> str:
    """Why this run's capture artifact cannot be measured, or `""` when it can.

    A version-1 artifact whose `canaries` list is empty passed every earlier gate
    and reported `MEASURED` with `ok=True` and `by_boundary()=={}` — the green
    verdict on zero evidence, reachable without malice when a builder silently
    drops every declared literal it cannot place. «Measured 0 of 0» and «nothing
    leaked» are different facts, and the first is the one that must be said."""
    if not captures:
        return (f"no {CAPTURE_SUFFIX} artifact in the run: a construction-time manifest "
                f"says what must not be there, and a run that persisted no delivered bytes "
                f"has nothing to scan it against. Reconstructing the bytes from the run's "
                f"mentions would measure the reconstruction, so this run is NOT_MEASURED")
    if not any(run.manifest.canaries for run in captures):
        return (f"{CAPTURE_ARTIFACT.replace('<run>', '…')} carries no manifest with canaries: "
                f"a manifest with no denominator is not measurable, and «measured, clean» on "
                f"zero evidence is the reading this refuses")
    return ""


def _expected_capture_keys(run_dir: pathlib.Path) -> tuple[frozenset[tuple[str, int]], int] | None:
    """Intervention arms recorded by the real runner, when its triple file exists."""
    paths = tuple(sorted(run_dir.glob("*.triples.jsonl")))
    if not paths:
        return None
    if len(paths) != 1:
        raise CaptureError(f"expected one triples artifact, found {len(paths)}")
    expected: set[tuple[str, int]] = set()
    seen: set[tuple[str, int]] = set()
    path = paths[0]
    try:
        with path.open(encoding="utf-8") as source:
            for number, line in enumerate(source, start=1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as error:
                    raise CaptureError(f"{path.name}:{number}: invalid triple JSON") from error
                if not isinstance(row, Mapping):
                    raise CaptureError(f"{path.name}:{number}: triple is not an object")
                case_id, repeat, arms = row.get("case_id"), row.get("repeat"), row.get("arms")
                if (not isinstance(case_id, str) or not case_id
                        or not isinstance(repeat, int) or isinstance(repeat, bool)
                        or not isinstance(arms, Mapping)):
                    raise CaptureError(f"{path.name}:{number}: invalid triple identity or arms")
                key = (case_id, repeat)
                if key in seen:
                    raise CaptureError(f"{path.name}:{number}: duplicate triple {key!r}")
                seen.add(key)
                if row.get("status") == "complete" and "I" not in arms:
                    raise CaptureError(f"{path.name}:{number}: complete triple has no I arm")
                if "I" in arms:
                    expected.add(key)
    except (OSError, UnicodeDecodeError) as error:
        raise CaptureError(f"{path.name}: could not be read ({type(error).__name__})") from error
    return frozenset(expected), len(seen)


def check_run(run_dir: pathlib.Path) -> CanaryReport:
    """Scan the SAVED bytes of one run — but ONLY against its own manifest.

    THE ARTIFACT IS THE EVIDENCE. A measurable run carries a versioned
    `<run>.canary.jsonl` written at capture time, one row per (case, repeat) with
    the manifest the case was built against and the EXACT bytes the gateway
    handed each boundary, the composed `model_request` included. The older reader
    paired a manifest with `model_input` it REBUILT from the run's
    detector-derived `mentions` and never built `model_request` at all, so
    dropping a manifest into any saved run measured the reconstruction under
    test. It no longer exists on this path.

    NO CAPTURE, NO MEASUREMENT — even with a manifest planted beside it, and even
    with a corpus present. The bytes are not derivable from anything else the run
    writes; that is what makes them evidence rather than a second copy of the
    masker's input.

    AN EMPTY HERD IS NOT A CLEAN RUN either: a known-version artifact that
    declares zero canaries has no denominator, so `ok=True` about it would be the
    green verdict on zero evidence. Refused here, and refused in `scan` too, so
    no entry point can turn «planted nothing» into «no leaks»."""
    manifest, problem = load_manifest(run_dir)
    if problem:
        return not_measured(problem)
    try:
        captures, skipped = read_captures_detailed(run_dir)
    except CaptureError as broken:
        return not_measured(f"the delivered bytes could not be read: {broken}")
    except Exception as error:  # noqa: BLE001 — an unreadable run is unmeasured, not clean
        return not_measured(f"the saved bytes could not be read: {type(error).__name__}: {error}")
    if skipped:
        # A partial read is NOT full coverage: name the skipped rows and keep
        # the denominator. No partial read may be reported as full-coverage
        # quality.
        try:
            coverage = _expected_capture_keys(run_dir)
        except CaptureError:
            coverage = None
        rows = len(expected) if (coverage is not None and (expected := coverage[0]) is not None) else len(captures)
        return replace(not_measured(f"capture read skipped {len(skipped)} row(s): {skipped[:5]!r}"),
                       coverage_known=coverage is not None, capture_rows=len(captures),
                       intervention_rows=rows, selected_rows=(coverage[1] if coverage else 0))
    empty = _capture_problem(captures)
    if empty:
        # AN OLD SAVED RUN HAS A DENOMINATOR TOO. The triples journal names the
        # 450 intervention arms the runner executed, and a run that persisted no
        # capture artifact is «0 of those 450 measured» — NOT_MEASURED, never
        # clean, but with the denominator the journal itself derives. Dropping
        # it makes an unmeasured run indistinguishable from an empty one, which
        # is exactly the «measured 0 of 0» reading this redesign exists to
        # forbid. `_expected_capture_keys` reads the same journal; ask it here
        # instead of skipping it on the early return.
        if not captures:
            try:
                coverage = _expected_capture_keys(run_dir)
            except CaptureError:
                coverage = None
            if coverage is not None:
                expected, selected = coverage
                return replace(not_measured(empty),
                               coverage_known=True, capture_rows=0,
                               intervention_rows=len(expected),
                               selected_rows=selected)
        return not_measured(empty)
    try:
        coverage = _expected_capture_keys(run_dir)
    except CaptureError as broken:
        return not_measured(f"the triple denominator could not be read: {broken}")
    if coverage is not None:
        expected, selected = coverage
        captured = frozenset((one.case_id, one.repeat) for one in captures)
        missing = expected - captured
        unexpected = captured - expected
        if missing or unexpected:
            return replace(not_measured(
                f"capture coverage {len(captured & expected)}/{len(expected)} I arms; "
                f"missing {sorted(missing)!r}; unexpected {sorted(unexpected)!r}"),
                coverage_known=True, capture_rows=len(captures),
                intervention_rows=len(expected), selected_rows=selected)
        return replace(merge_reports(scan_captures(captures, manifest)),
                       coverage_known=True, capture_rows=len(captures),
                       intervention_rows=len(expected), selected_rows=selected)
    return replace(merge_reports(scan_captures(captures, manifest)),
                   capture_rows=len(captures))


def _manifest_problem(raw: Mapping[str, object]) -> str:
    """Why this manifest artifact is unusable, or `""` when it reads.

    Split out of `load_manifest` so `check_run` can answer «no manifest» and
    «an unreadable manifest» with the SAME sentence, from the same code: two
    readers of one file is how a future format ends up accepted in one path and
    refused in another."""
    try:
        version = int(raw.get("version", -1))
    except (TypeError, ValueError):
        version = -1
    if version != MANIFEST_VERSION:
        return (f"{MANIFEST_ARTIFACT} declares version {raw.get('version')!r}, and "
                f"this reader knows only {MANIFEST_VERSION}: a manifest read with "
                f"the wrong field meanings would decide leaks from a surface the "
                f"fixture never planted")
    if manifest_from_json(raw) is None:
        return (f"{MANIFEST_ARTIFACT} is present and version {version}, but its body "
                f"is malformed — it is unmeasured, not empty")
    return ""


def load_manifest(run_dir: pathlib.Path) -> tuple[CanaryManifest | None, str]:
    """The versioned artifact of a saved run, AND why there is none.

    TWO KINDS OF «NO MANIFEST» ARE NOT ONE SENTENCE. A missing file and a file
    whose version this reader does not know both yield `None`, and they used to
    yield the same reason — an operator sent looking for a file that is present,
    with the future format reading as a deletion. The pair is returned rather
    than the bare manifest so the diagnosis survives to `check_run`, where the
    operator reads it."""
    path = run_dir / MANIFEST_ARTIFACT
    if not path.exists():
        return None, ""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return None, (f"{MANIFEST_ARTIFACT} is present but could not be read as JSON: "
                      f"{type(error).__name__}: {error}")
    if not isinstance(raw, Mapping):
        return None, f"{MANIFEST_ARTIFACT} is present but is not a JSON object"
    problem = _manifest_problem(raw)
    if problem:
        return None, problem
    return manifest_from_json(raw), ""


def _delivered_from_run(run_dir: pathlib.Path) -> tuple[CapturedPayload, ...] | None:
    """The delivered bytes a saved run really holds, flattened over its captures.

    THE BYTES COME FROM THE CAPTURE ARTIFACT AND FROM NOWHERE ELSE. This reader
    used to rebuild `model_input` by re-applying the substitutes in the run's
    `mentions` (detector-derived records) onto the corpus messages, and it never
    built the composed `model_request` at all — so a manifest was scored against
    the masking under test rather than against what the model was sent. It now
    reads the exact bytes the gateway persisted, including the composed request.

    `None` means «this run carries no capture artifact», which `check_run` turns
    into NOT_MEASURED: a manifest with nothing to pair it with is not a
    measurement, however plausible the reconstruction would have looked."""
    captures = read_captures(run_dir)
    if not captures:
        return None
    return tuple(CapturedPayload(name=one.name, text=one.text, real_text=one.real_text)
                 for run in captures for one in run.delivered)
