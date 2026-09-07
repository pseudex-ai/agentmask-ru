"""Every diverging triple of a run under the microscope, with its context.

    python3 bench/agentpii4/microscope.py bench/runs/<date>/v4-live-small [--out microscope.md]

`autopsy.py` gives one line per triple; this gives everything a reader needs to
name the ROOT cause without opening `arms.jsonl` by hand: the customer's turns,
what the model was shown in place of each value (or that it saw the REAL value
— a LEAK, which the three levels of the report cannot see because a leaked
value makes the two arms AGREE), every call of both arms with what the gateway
restored, every field verdict, and the reply. Nothing here re-runs a model.

Two things are added to the autopsy's causes:

  * a LEAK column — a personal datum in a message the I arm never saw a
    substitute for. The report scores agreement; a value that reached the
    model in the clear reaches the tool in the clear too, and the arms agree.
    That is the one failure the product exists to prevent, and it was
    invisible in every number the run printed.
  * NAME and LOC field sub-causes read with morphology: the same lemma in
    another case (`name_case`), a different lemma for one surface
    (`name_lemma` — «марину» kept as «марин»), a settlement-only difference
    in an address (`loc_city`), a fake piece that reached the tool
    (`loc_fake`, `name_fake`).
"""
import argparse
import re
import sys
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from bench.agentpii4.autopsy import _cause, _load_run  # noqa: E402
from bench.agentpii4.compare import compare_triple  # noqa: E402
from bench.agentpii4.parts import parts_of  # noqa: E402
from bench.agentpii4.schema import message_text  # noqa: E402
from pseudex.morph_places import MORPH  # noqa: E402  (morphology only; no detection, no vault)


def _lemmas(word: str) -> set[str]:
    return {p.normal_form for p in MORPH.parse(word.strip().casefold().replace("ё", "е"))}


def _field_cause(f, substitutes: dict) -> str:
    """A finer label for one diverging field, from the recorded strings."""
    ref = " ".join(str(f.ref).split()).casefold().replace("ё", "е")
    obs = " ".join(str(f.obs).split()).casefold().replace("ё", "е")
    pieces = {p.casefold().replace("ё", "е")
              for surface, parts in substitutes.values() for p in [surface, *parts.values()] if p}
    if f.kind == "agree":
        return ""
    if f.kind in ("absent", "extra"):
        return f"{f.kind}:{f.path.rsplit('.', 1)[-1]}"
    if f.kind in ("derived", "control_erred", "validated_refused", "ref_refused"):
        return f.kind
    if obs and obs in pieces:
        return f"{f.pii_type.lower()}_fake"
    if f.pii_type == "NAME" and ref and obs:
        if ref == obs:
            return "name_same"
        rw, ow = ref.split(), obs.split()
        if len(rw) == len(ow) and all(_lemmas(a) & _lemmas(b) for a, b in zip(rw, ow)):
            return "name_case"
        if set(rw) & set(ow):
            return "name_partial"
        return "name_lemma"
    if f.pii_type == "LOC" and ref and obs:
        rp, op = parts_of("LOC", str(f.ref)), parts_of("LOC", str(f.obs))
        diff = {k for k in set(rp) | set(op) if rp.get(k, "") != op.get(k, "")}
        if diff == {"city"}:
            return "loc_city"
        if diff and diff <= {"street"}:
            return "loc_street"
        if diff and diff <= {"house", "flat", "entrance", "building"}:
            return "loc_number"
        return "loc_other"
    if f.pii_type == "PHONE" and re.sub(r"\D", "", ref) == re.sub(r"\D", "", obs):
        return "phone_format"
    return f"{f.kind}{('/' + f.sub) if f.sub else ''}"


def _short(text: object, n: int = 160) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[:n - 1] + "…"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir")
    parser.add_argument("--out", default="microscope.md")
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    corpus, triples, excluded = _load_run(run_dir)

    lines: list[str] = [f"# Микроскоп — {run_dir.name}", ""]
    causes: Counter[str] = Counter()
    field_causes: Counter[str] = Counter()
    leaks: Counter[str] = Counter()
    leak_rows: list[str] = []
    seen_items = 0
    dumped = 0
    for triple in sorted(triples, key=lambda t: (t.case_id, t.repeat)):
        case = corpus[triple.case_id]
        ic, cc = compare_triple(case, triple)
        in_messages = [item for item in case.pii if item.where.kind == "message"]
        seen_items += len(in_messages)
        leaked = [item for item in in_messages if item.id not in triple.I.substitutes]
        for item in leaked:
            leaks[f"{item.type}/{case.register}"] += 1
            leak_rows.append(f"| {triple.case_id}\\|{triple.repeat} | {case.register} | {item.type} | `{_short(item.value, 60)}` | "
                             f"`{_short(message_text(case, item.where.msg), 110)}` |")
        if ic.levels.state and not leaked:
            continue
        dumped += 1
        fields = list(ic.fields)
        cause = _cause(case, triple, fields) if not ic.levels.state else "leak-only"
        causes[cause] += 1
        lines.append(f"## {triple.case_id}|{triple.repeat} · {case.kind} · {case.register} · "
                     f"L1 {'=' if ic.levels.tools else '≠'} · L3 {'=' if ic.levels.state else '≠'} · "
                     f"C′≈C {'да' if cc.levels.state else 'нет'} · причина: **{cause}**")
        for index, message in enumerate(case.messages):
            if message.role == "user":
                lines.append(f"- USER[{index}]: {_short(message.content, 400)}")
        for item in in_messages:
            shown = triple.I.substitutes.get(item.id)
            if shown is None:
                lines.append(f"- **LEAK** {item.type} `{item.value}` — модель видела настоящее значение")
            else:
                lines.append(f"- seen {item.type} `{item.value}` → `{shown[0]}`")
        for label, run in (("C", triple.C), ("I", triple.I), ("C′", triple.C2)):
            if not run.calls:
                lines.append(f"- {label}: — (без вызовов)")
            for call in run.calls:
                if label == "I":
                    lines.append(f"- I: `{call.name}` written={_short(call.written, 260)} → restored={_short(call.restored, 260)}"
                                 + (f" · residual={call.residual}" if call.residual else "")
                                 + (f" · refusal={call.refusal_rule}" if call.refusal_rule else ""))
                else:
                    lines.append(f"- {label}: `{call.name}` {_short(call.written, 200)}"
                                 + (f" · refusal={call.refusal_rule}" if call.refusal_rule else ""))
        for f in fields:
            if f.kind == "agree":
                continue
            fc = _field_cause(f, triple.I.substitutes)
            field_causes[fc] += 1
            lines.append(f"- FIELD `{f.tool}.{f.path}` [{f.kind}{('/' + f.sub) if f.sub else ''} → {fc}] "
                         f"C=`{_short(f.ref, 80)}` I=`{_short(f.obs, 80)}`" + (f" · {f.why}" if f.why else ""))
        lines.append(f"- REPLY I: {_short(triple.I.reply, 300)}")
        lines.append("")

    head = [f"троек: {len(triples)} · разобрано: {dumped} · исключено: {len(excluded)}", "",
            "## Причины (по тройкам)", "", "| причина | троек |", "|---|---|"]
    head += [f"| {c} | {n} |" for c, n in causes.most_common()]
    head += ["", "## Поля (по расходящимся полям)", "", "| подпричина | полей |", "|---|---|"]
    head += [f"| {c} | {n} |" for c, n in field_causes.most_common()]
    head += ["", f"## УТЕЧКИ В МОДЕЛЬ — {sum(leaks.values())} из {seen_items} значений в сообщениях", "",
             "| тип/регистр | значений |", "|---|---|"]
    head += [f"| {c} | {n} |" for c, n in leaks.most_common()]
    head += ["", "| тройка | регистр | тип | значение | реплика |", "|---|---|---|---|---|"] + leak_rows + [""]
    out = run_dir / args.out
    out.write_text("\n".join(lines[:2] + head + lines[2:]) + "\n", encoding="utf-8")
    print("\n".join(head[: 8 + len(causes) + 6 + len(field_causes) + 6 + len(leaks)]))
    print(f"\nзаписано {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
