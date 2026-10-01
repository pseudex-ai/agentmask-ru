"""M1b probe 3 — the parity divergence's CLASS, with positive and negative
controls, on the pinned unchanged build, in memory, no provider.

The four saved divergences could not be replayed to a failure (see
`probe_parity_replay.py`): their failing push mints substitutes that no artifact
persists. That leaves the mechanism undecided, and this probe decides as much of
it as the code allows without inventing a cause.

`RealGateway._push` compares two implementations of the same masking on the SAME
message:
    observed = bench.agentpii3.score._mask_message(text, detector, view, role)
    content  = envelope.mask_messages(whole_transcript, context, False)[-1]
and raises when they differ. They are not the same function. Production reads its
echo/provenance record from a SNAPSHOT taken at the start of the pass and applies
the call-scoped `_reserve_echoes` leg when a result is bound to a preceding call;
the scorer has no call association, reads the vault live, and computes its LOC
cover set from the pieces IT kept. The controls below ask whether that difference
is observable at all on a `tool` message:

  POSITIVE  a tool result that introduces a value the transcript has not seen;
  NEGATIVE  a tool result with no personal data at all;
  ECHO      a tool result that repeats a substitute the transcript already shows.

A negative that stays equal is what makes the positive's difference MEANINGFUL
rather than an artefact of calling two functions at all. The probe reports the
first differing offset, never a cause it did not observe.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "prototype"))

import testkit  # noqa: E402

testkit.load_dev_bundle()

from bench.agentpii3 import score  # noqa: E402
from bench.agentpii5.harness import GatewayV5, _ORG  # noqa: E402
from bench.agentpii5.schema import case_v5_from_json  # noqa: E402
from pseudex import envelope  # noqa: E402
from pseudex.audit import AuditLog  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.maskcache import MaskCache  # noqa: E402
from pseudex.vault import Vault  # noqa: E402


def compare(gateway: GatewayV5, wire: dict, text: str, index=None) -> dict:
    """The harness's own comparison, run without the transcript being appended
    by the gateway first — so both sides read the same wire."""
    observed = score._mask_message(text, gateway._detector, gateway._view,
                                   str(wire.get("role", "")))
    transcript = [dict(one) for one in gateway._transcript] + [dict(wire)]
    production = envelope.mask_messages(transcript, gateway._context, False)[-1]["content"]
    out = {"observed_len": len(observed.masked), "production_len": len(production),
           "equal": observed.masked == production}
    if not out["equal"]:
        at = next((k for k, (a, b) in enumerate(zip(observed.masked, production))
                   if a != b), min(len(observed.masked), len(production)))
        out["first_difference"] = at
        out["observed_window"] = observed.masked[max(0, at - 30):at + 40]
        out["production_window"] = production[max(0, at - 30):at + 40]
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--case", default="derive-008")
    parser.add_argument("--tool-args", default="")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    run_dir = pathlib.Path(args.run).resolve()
    corpus = json.loads((run_dir / "corpus.v5.json").read_text(encoding="utf-8"))
    case = case_v5_from_json(next(one for one in corpus["corpus"]
                                  if one["base"]["id"] == args.case))
    detector = Detector()

    # The saved substitutes are primed exactly as in `probe_parity_replay`, so
    # the transcript the controls are compared on is the run's own, not a
    # same-shaped one with different fakes.
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from probe_parity_replay import (load_captures, prime_from_captures,
                                     primed_vault_class)
    captures = load_captures(run_dir, {args.case})
    payloads = captures[args.case]["capture"]["payloads"]
    Vault._unique_token = primed_vault_class(prime_from_captures(case, payloads))

    gateway = GatewayV5(case, detector, Vault(":memory:", _ORG), AuditLog(":memory:"),
                        MaskCache(256), capture=True)
    gateway.push_system(case.base.messages[0].content)
    gateway.push_user(1)
    # THE FAILING PUSH'S OWN PREDECESSORS: the real path is
    # note_tool_call -> restore_arguments -> backend.call -> push_call, and the
    # restore is what makes the conversation's restored values available to the
    # tool leg. A control that skips it measures a state the run never had.
    if args.tool_args:
        saved = json.loads(pathlib.Path(args.tool_args).read_text(encoding="utf-8"))
        gateway.note_tool_call(str(saved["name"]), saved["arguments"])
        gateway.restore_arguments(saved["arguments"])

    transcript_json = json.dumps(gateway._transcript, ensure_ascii=False)
    positive = json.dumps(
        {"appointment_id": "apt-9", "status": "ACCEPTED",
         "patient": {"last_name": "Хабаров", "first_name": "Тимур",
                     "birth_date": "1979-03-04"},
         "phone": "+79995550101"}, ensure_ascii=False)
    negative = json.dumps(
        {"appointment_id": "apt-9", "status": "ACCEPTED", "queue": 14},
        ensure_ascii=False)
    seen = [value for item in case.base.pii for value in
            (item.value, item.canonical) if value]
    echo = json.dumps(
        {"appointment_id": "apt-9", "status": "booked",
         "patient": {"last_name": "Устинова", "first_name": "Юлия"},
         "phone": "+79184403785"}, ensure_ascii=False)
    fragments = {
        "fragment_surname": "Клиент: Соколова, статус подтверждён.",
        "fragment_phone_head": "Не дозвонились: +791669836, попробуйте позже.",
        "fragment_phone_tail": "Обратный номер: 916983686.",
        "fragment_patronymic": "Игоревна — так записано в карте.",
        "full_name_again": "Пациент: Соколова Анна Игоревна, запись подтверждена.",
    }

    controls = {
        "positive_new_value": compare(gateway, {"role": "tool", "name": "clinic_book",
                                                "content": positive}, positive),
        "negative_no_pii": compare(gateway, {"role": "tool", "name": "clinic_book",
                                             "content": negative}, negative),
        "echo_of_substitute": compare(gateway, {"role": "tool", "name": "clinic_book",
                                                "content": echo}, echo),
    }
    for name, text in fragments.items():
        controls[name] = compare(gateway, {"role": "tool", "name": "clinic_book",
                                           "content": text}, text)
    differing = [name for name, one in controls.items() if not one["equal"]]
    report = {
        "case": args.case,
        "run_dir": str(run_dir),
        "transcript_sha256_len": len(transcript_json),
        "real_values_in_transcript": seen,
        "controls": controls,
        "positive_differs": not controls["positive_new_value"]["equal"],
        "negative_equal": controls["negative_no_pii"]["equal"],
        "echo_equal": controls["echo_of_substitute"]["equal"],
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    pathlib.Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
