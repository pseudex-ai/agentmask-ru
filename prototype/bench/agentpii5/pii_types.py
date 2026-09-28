# pii_types.py — the single home of the PII type registry (spec tz-agentpii6.md
# §1.0, §8.1). Every fact a generator, a schema or a test reads about a type
# lives HERE as one frozen `TypeSpec`, never as a literal sprinkled across
# `contracts`, `form`, `observe`, `perfect`, `judge` or `metrics`.
#
# Why this file and not `types.py`: the name `types` would shadow the standard
# library module and break every `import types` downstream. Why `NEEDLE_KINDS`
# lives here and `contracts` re-exports it: `pii_types` must never import
# `contracts` (which imports the engine-side tool registry and the v4 tables),
# so the direction of the edge is `contracts -> pii_types`, never the reverse.
#
# This module is a PURE, deterministic description. It imports nothing from
# `pseudex`, nothing from `licensing`, nothing from this package's other
# modules. `test_pii_types.test_no_engine` pins that in a fresh process.

from __future__ import annotations

from dataclasses import dataclass


# The shapes a value survives being rewritten in (contracts §4bis). Closed,
# because a metric that could not name the shape it matched on could not be
# argued with. Moved here so the registry can own the closed list (§8.1 CQ-2).
NEEDLE_KINDS: tuple[str, ...] = ("whole", "stem", "digits", "date", "initials", "squeezed")

# The two origins a record may carry. A v5 record reproduces today's tables
# byte-for-byte; a v6 record adds a new item type.
ORIGIN_V5: str = "v5"
ORIGIN_V6: str = "v6"

# The class labels §1.0 names. `v5` is the ten item types plus DATE, none of
# whose semantics v6 redecides; `C`/`K`/`KC` are assertions about a NEW type.
TYPE_CLASS_V5: str = "v5"
TYPE_CLASS_C: str = "C"
TYPE_CLASS_K: str = "K"
TYPE_CLASS_KC: str = "KC"


@dataclass(frozen=True)
class TypeSpec:
    """One type, one record. Frozen, no defaults: a fact is written here once
    and the generator, the schema and the tests all read this same object.
    Field groups follow `tz-agentpii6.md` §1.0."""

    # identity
    id: str
    origin: str                       # ORIGIN_V5 | ORIGIN_V6
    item_type: bool                   # False only for DATE (a non-item date)
    # class and checksum
    type_class: str                   # TYPE_CLASS_* — an assertion, not realism
    generated_checksum: str           # published algorithm name, or ""
    bare_typed: bool                  # bare value is a positive with its own floor
    # grammar
    grammar: str                      # regex + variants, or "" for a v5 type
    length: str                       # range with source, or ""
    grammar_status: str               # "ГОТОВ" | "ГРАММАТИКА?" | "ДЕРЖИМ"
    # where it occurs
    cues: tuple[str, ...]
    field_keys: tuple[str, ...]
    industries: tuple[str, ...]
    pd_context: str                   # the OD-22/23/24 rule, or ""
    # form
    form_features: tuple[str, ...]
    feature_labels: tuple[tuple[str, tuple[str, ...]], ...]   # (feature, labels) in table order
    abstain: tuple[tuple[str, str], ...]                      # (feature, abstain label) pairs
    identifying_roles: tuple[str, ...]
    # search and comparison
    needle_kinds: tuple[str, ...]     # subset of NEEDLE_KINDS; "whole" always
    squeeze_separators: str           # the separator class for a squeezed needle, or ""
    signature_tail: int               # tail digits of the signature (10 for PHONE)
    value_notation: str               # "digits"|"date"|"squeezed"|"glyph_fold"|"ip_strict"|""
    # gateways and judge
    engine_labels: tuple[str, ...]    # the engine's own labels, never another element type
    mint: str                         # the perfect-gateway mint rule id, or ""
    hunt: str                         # "always"|"by_shape"|"covered"|""
    sample: str                       # a representative value for T4/T8 and W0-R8


# --- the eleven v5 records, in today's FORM_FEATURES order (§8.1) -----------------
#
# The order is load-bearing: `FORM_FEATURES` is built from this tuple and the
# histogram order in the report follows it. The values transcribe the literals
# that live in `contracts.py` today; `test_pii_types.test_v5_tables_reproduced`
# proves the derivatives equal those literals byte-for-byte.

TYPE_REGISTRY: tuple[TypeSpec, ...] = (
    TypeSpec(
        id="NAME", origin=ORIGIN_V5, item_type=True, type_class=TYPE_CLASS_V5,
        generated_checksum="", bare_typed=False, grammar="", length="", grammar_status="ГОТОВ",
        cues=(), field_keys=(), industries=(), pd_context="",
        form_features=("case_class", "gram_case", "order", "parts", "initials", "script", "hyphen_particle"),
        feature_labels=(
            ("case_class", ("lower", "title", "upper", "mixed", "none")),
            ("gram_case", ("nomn", "gent", "datv", "accs", "ablt", "loct", "unknown")),
            ("order", ("F-I-O", "I-F", "I-O-F", "single", "other")),
            ("parts", ("1", "2", "3", "4+")),
            ("initials", ("none", "given", "given_patronymic")),
            ("script", ("cyrillic", "latin:gost", "latin:icao", "latin:bgn", "latin:unknown", "mixed", "none")),
            ("hyphen_particle", ("none", "hyphen", "particle", "both")),
        ),
        abstain=(("gram_case", "unknown"), ("case_class", "none"), ("script", "none"), ("order", "other")),
        identifying_roles=("surname", "given", "patronymic"),
        needle_kinds=("whole", "stem", "initials"), squeeze_separators="", signature_tail=0, value_notation="",
        engine_labels=(), mint="", hunt="", sample="Иванов Пётр Сергеевич",
    ),
    TypeSpec(
        id="PHONE", origin=ORIGIN_V5, item_type=True, type_class=TYPE_CLASS_V5,
        generated_checksum="", bare_typed=False, grammar="", length="", grammar_status="ГОТОВ",
        cues=(), field_keys=(), industries=(), pd_context="",
        form_features=("prefix", "grouping", "separators", "parens"),
        feature_labels=(
            ("prefix", ("plus7", "eight", "seven", "bare", "other")),
            ("grouping", ("3-3-2-2", "3-3-4", "solid", "other")),
            ("separators", ("none", "space", "hyphen", "dot", "mixed")),
            ("parens", ("yes", "no")),
        ),
        abstain=(),
        identifying_roles=("digits",),
        needle_kinds=("whole", "digits"), squeeze_separators="", signature_tail=10, value_notation="digits",
        engine_labels=(), mint="", hunt="", sample="+7 999 123-45-67",
    ),
    TypeSpec(
        id="LOC", origin=ORIGIN_V5, item_type=True, type_class=TYPE_CLASS_V5,
        generated_checksum="", bare_typed=False, grammar="", length="", grammar_status="ГОТОВ",
        cues=(), field_keys=(), industries=(), pd_context="",
        form_features=("case_class", "generic", "generic_position", "house_marker", "flat_marker", "commas",
                       "city_present", "city_position", "by_fields", "building_entrance_markers"),
        feature_labels=(
            ("case_class", ("lower", "title", "upper", "mixed", "none")),
            ("generic", ("none", "full:*", "abbr:*")),
            ("generic_position", ("before", "after", "none")),
            ("house_marker", ("none", "d_dot_space", "d_dot_nospace", "d_nodot", "dom", "other")),
            ("flat_marker", ("none", "kv_dot_space", "kv_dot_nospace", "kv_nodot", "kvartira", "other")),
            ("commas", ("yes", "no")),
            ("city_present", ("yes", "no")),
            ("city_position", ("first", "last", "middle", "none")),
            ("by_fields", ("fields", "string")),
            ("building_entrance_markers", ("none", "markers:*")),
        ),
        abstain=(("generic_position", "none"), ("case_class", "none")),
        identifying_roles=("street",),
        needle_kinds=("whole", "stem"), squeeze_separators="", signature_tail=0, value_notation="",
        engine_labels=(), mint="", hunt="", sample="г Самара, ул Луговая, д 10",
    ),
    TypeSpec(
        id="DOB", origin=ORIGIN_V5, item_type=True, type_class=TYPE_CLASS_V5,
        generated_checksum="", bare_typed=False, grammar="", length="", grammar_status="ГОТОВ",
        cues=(), field_keys=(), industries=(), pd_context="",
        form_features=("notation", "separator", "padding", "year_len", "month_form"),
        feature_labels=(
            ("notation", ("dmy_dots", "dmy_slashes", "iso", "words", "solid", "other")),
            ("separator", ("dot", "slash", "hyphen", "space", "none")),
            ("padding", ("padded", "unpadded")),
            ("year_len", ("2", "4", "none")),
            ("month_form", ("number", "word_nominative", "word_genitive")),
        ),
        abstain=(),
        identifying_roles=("iso",),
        needle_kinds=("whole", "date"), squeeze_separators="", signature_tail=0, value_notation="date",
        engine_labels=(), mint="", hunt="", sample="14.03.1987",
    ),
    TypeSpec(
        id="DATE", origin=ORIGIN_V5, item_type=False, type_class=TYPE_CLASS_V5,
        generated_checksum="", bare_typed=False, grammar="", length="", grammar_status="ГОТОВ",
        cues=(), field_keys=(), industries=(), pd_context="",
        form_features=("notation", "separator", "padding", "year_len", "month_form"),
        feature_labels=(
            ("notation", ("dmy_dots", "dmy_slashes", "iso", "words", "solid", "other")),
            ("separator", ("dot", "slash", "hyphen", "space", "none")),
            ("padding", ("padded", "unpadded")),
            ("year_len", ("2", "4", "none")),
            ("month_form", ("number", "word_nominative", "word_genitive")),
        ),
        abstain=(),
        identifying_roles=("iso",),
        needle_kinds=("whole", "date"), squeeze_separators="", signature_tail=0, value_notation="date",
        engine_labels=(), mint="", hunt="", sample="14.03.1987",
    ),
    TypeSpec(
        id="EMAIL", origin=ORIGIN_V5, item_type=True, type_class=TYPE_CLASS_V5,
        generated_checksum="", bare_typed=False, grammar="", length="", grammar_status="ГОТОВ",
        cues=(), field_keys=(), industries=(), pd_context="",
        form_features=("case_class",),
        feature_labels=(("case_class", ("lower", "upper", "mixed", "none")),),
        abstain=(("case_class", "none"),),
        identifying_roles=("local",),
        needle_kinds=("whole", "stem"), squeeze_separators="", signature_tail=0, value_notation="",
        engine_labels=(), mint="", hunt="", sample="ivanov.petr@example.ru",
    ),
    TypeSpec(
        id="CARD", origin=ORIGIN_V5, item_type=True, type_class=TYPE_CLASS_V5,
        generated_checksum="", bare_typed=False, grammar="", length="", grammar_status="ГОТОВ",
        cues=(), field_keys=(), industries=(), pd_context="",
        form_features=("grouping", "separator"),
        feature_labels=(
            ("grouping", ("4x4", "solid", "other")),
            ("separator", ("space", "hyphen", "none", "other")),
        ),
        abstain=(),
        identifying_roles=("digits",),
        needle_kinds=("whole", "digits"), squeeze_separators="", signature_tail=0, value_notation="digits",
        engine_labels=(), mint="", hunt="", sample="4111 1111 1111 1111",
    ),
    TypeSpec(
        id="SNILS", origin=ORIGIN_V5, item_type=True, type_class=TYPE_CLASS_V5,
        generated_checksum="", bare_typed=False, grammar="", length="", grammar_status="ГОТОВ",
        cues=(), field_keys=(), industries=(), pd_context="",
        form_features=("separators",),
        feature_labels=(("separators", ("canonical", "solid", "other")),),
        abstain=(),
        identifying_roles=("digits",),
        needle_kinds=("whole", "digits"), squeeze_separators="", signature_tail=0, value_notation="digits",
        engine_labels=(), mint="", hunt="", sample="123-456-789 01",
    ),
    TypeSpec(
        id="INN", origin=ORIGIN_V5, item_type=True, type_class=TYPE_CLASS_V5,
        generated_checksum="", bare_typed=False, grammar="", length="", grammar_status="ГОТОВ",
        cues=(), field_keys=(), industries=(), pd_context="",
        form_features=("length", "separators"),
        feature_labels=(
            ("length", ("10", "12", "other")),
            ("separators", ("none", "space", "other")),
        ),
        abstain=(),
        identifying_roles=("digits",),
        needle_kinds=("whole", "digits"), squeeze_separators="", signature_tail=0, value_notation="digits",
        engine_labels=(), mint="", hunt="", sample="7707083893",
    ),
    TypeSpec(
        id="PASSPORT", origin=ORIGIN_V5, item_type=True, type_class=TYPE_CLASS_V5,
        generated_checksum="", bare_typed=False, grammar="", length="", grammar_status="ГОТОВ",
        cues=(), field_keys=(), industries=(), pd_context="",
        form_features=("series_number_split",),
        feature_labels=(("series_number_split", ("2-2-6", "4-6", "solid", "other")),),
        abstain=(),
        identifying_roles=("digits",),
        needle_kinds=("whole", "digits"), squeeze_separators="", signature_tail=0, value_notation="digits",
        engine_labels=(), mint="", hunt="", sample="45 09 123456",
    ),
    TypeSpec(
        id="PLATE", origin=ORIGIN_V5, item_type=True, type_class=TYPE_CLASS_V5,
        generated_checksum="", bare_typed=False, grammar="", length="", grammar_status="ГОТОВ",
        cues=(), field_keys=(), industries=(), pd_context="",
        form_features=("case_class", "spaces", "region_sep"),
        feature_labels=(
            ("case_class", ("lower", "upper", "mixed", "none")),
            ("spaces", ("yes", "no")),
            ("region_sep", ("space", "none", "other")),
        ),
        abstain=(("case_class", "none"),),
        identifying_roles=(),
        needle_kinds=("whole", "squeezed"), squeeze_separators="", signature_tail=0, value_notation="squeezed",
        engine_labels=(), mint="", hunt="", sample="А123БВ 77",
    ),
)


# Collision clusters (tz-agentpii6.md §1.7). Empty until the first v6 type is
# admitted: a cluster names two same-form values that a cue/key must tell apart.
CLUSTERS: dict[str, frozenset[str]] = {}


# The new item types: records with item_type and origin == "v6". R02 admits
# exactly these, and the orchestrator's reg_types reads exactly these. Empty in
# the first Phase-1 package (no v6 case yet).
NEW_ITEM_TYPES: tuple[str, ...] = tuple(
    t.id for t in TYPE_REGISTRY if t.item_type and t.origin == ORIGIN_V6
)


# --- derivatives: pure functions with the registry as a parameter ----------------
#
# Why functions and not module constants: a component or a test that holds a
# BROKEN copy of the registry must be able to see its own tables, and
# `registry_problems` must judge that copy, not the live one. The live tables in
# `contracts.py` call these with `TYPE_REGISTRY`.

def form_features(registry: tuple[TypeSpec, ...]) -> dict[str, tuple[str, ...]]:
    return {t.id: t.form_features for t in registry}


def form_types(registry: tuple[TypeSpec, ...]) -> tuple[str, ...]:
    return tuple(t.id for t in registry)


def feature_labels(registry: tuple[TypeSpec, ...]) -> dict[tuple[str, str], tuple[str, ...]]:
    out: dict[tuple[str, str], tuple[str, ...]] = {}
    for t in registry:
        for feature, labels in t.feature_labels:
            out[(t.id, feature)] = labels
    return out


def form_abstain(registry: tuple[TypeSpec, ...]) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for t in registry:
        for feature, label in t.abstain:
            out[(t.id, feature)] = label
    return out


def identifying_roles(registry: tuple[TypeSpec, ...]) -> dict[str, tuple[str, ...]]:
    return {t.id: t.identifying_roles for t in registry}


def digit_piece_types(registry: tuple[TypeSpec, ...]) -> frozenset[str]:
    return frozenset(t.id for t in registry if "digits" in t.needle_kinds)


def date_piece_types(registry: tuple[TypeSpec, ...]) -> frozenset[str]:
    return frozenset(t.id for t in registry if "date" in t.needle_kinds)


def derived_piece_types(registry: tuple[TypeSpec, ...]) -> frozenset[str]:
    # A type whose value a model rewrites in another alphabet or squeezes to
    # initials: declared `script` or `initials` among its form features. NAME
    # alone among the v5 records.
    return frozenset(t.id for t in registry
                     if "script" in t.form_features or "initials" in t.form_features)


def squeezed_types(registry: tuple[TypeSpec, ...]) -> frozenset[str]:
    return frozenset(t.id for t in registry if "squeezed" in t.needle_kinds)


# --- the registry rules T1–T8 (tz-agentpii6.md §8.1) ----------------------------
#
# Each returns every violation as its rule id string, never just the first, so a
# component can fix one and still see the rest. T4 is not here: «a sample
# survives in itself» is a property of the needle layer and is pinned by
# `test_pii_types.test_every_type_survives_in_itself` (W0-R8), not by this module.

def _rule(ok: bool, name: str) -> list[str]:
    return [] if ok else [name]


def registry_problems(registry: tuple[TypeSpec, ...]) -> list[str]:
    problems: list[str] = []
    for t in registry:
        # T1 — every feature carries >= 2 labels (else an isolating pair cannot exist).
        for feature, labels in t.feature_labels:
            if len(labels) < 2:
                problems.append(f"T1 {t.id}.{feature} has {len(labels)} label(s)")
        # T2 — needle kinds are a subset of NEEDLE_KINDS and `whole` is always present.
        for kind in t.needle_kinds:
            if kind not in NEEDLE_KINDS:
                problems.append(f"T2 {t.id} needle kind {kind!r} not in NEEDLE_KINDS")
        if "whole" not in t.needle_kinds:
            problems.append(f"T2 {t.id} has no 'whole' needle")
        # T3 — `stem` iff identifying roles are non-empty AND no digits/date kind.
        has_stem = "stem" in t.needle_kinds
        has_digit_or_date = "digits" in t.needle_kinds or "date" in t.needle_kinds
        if has_stem != (bool(t.identifying_roles) and not has_digit_or_date):
            problems.append(f"T3 {t.id} stem/roles mismatch")
        # T5 — a named checksum must have a mint and a sample pinned.
        if t.generated_checksum and (not t.mint or not t.sample):
            problems.append(f"T5 {t.id} generated_checksum without mint/sample")
        # T6 — a [K] type must carry cues or field keys (or be bare_typed).
        if t.type_class == TYPE_CLASS_K and not t.bare_typed and not t.cues and not t.field_keys:
            problems.append(f"T6 {t.id} [K] without cue/key")
        # T7 — engine_labels must not name another ELEMENT type (DOB/DATE are the
        # one declared equivalence, and DATE is not an item type so it can never
        # be «another element type»).
        element_ids = {u.id for u in registry if u.item_type}
        for label in t.engine_labels:
            if label in element_ids and label != t.id and label != "DOB" and label != "DATE":
                problems.append(f"T7 {t.id} engine label {label!r} names another element type")
        # T8 — a minted substitute must pass the grammar, share no alphanumeric
        # position with the sample, and fail the checksum. Checked only when a
        # mint rule and a sample are both present; the arithmetic itself lives in
        # `perfect`/`checksum_v6`, so this is a presence guard, not a third check.
        if t.mint and not t.sample:
            problems.append(f"T8 {t.id} mint without sample")
    # The clusters must name types that exist in the registry.
    ids = {t.id for t in registry}
    for cluster_id, members in CLUSTERS.items():
        for member in members:
            if member not in ids:
                problems.append(f"cluster {cluster_id} names unknown type {member!r}")
    return problems
