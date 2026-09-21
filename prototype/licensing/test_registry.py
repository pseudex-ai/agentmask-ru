"""Реестр версий: каждое обещание ТЗ (D-054…D-057, D-061) как проверка.

Что здесь пинится и почему это не формальность:

- `validate` отвергает файл без дайджеста, с алиасом `latest` не на новейшем
  цикле, с `eol` без уведомления за 90 дней — три способа, которыми реестр
  соврал бы серверу и сайту молча;
- `record` на patch двигает только `latest` цикла; на новом миноре открывает
  цикл, закрывает прежний (maintenance, eol через 6 месяцев, объявлен сегодня)
  и переносит `X`/`latest`;
- `aliases_for` на maintenance-патче возвращает только `X.Y`;
- `verdict` для `1.0.0` (что говорил КАЖДЫЙ образ до D-053) — старейший цикл,
  не «новее новейшего»;
- `check` отвечает 426 только после eol, объявленного вовремя; поздний eol —
  «late», не отказ (D-056, урок Docker 29.0 → 29.3).

    python3 -m licensing.test_registry
"""

import datetime as dt
import json
import tempfile
from pathlib import Path

from licensing import registry

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))
    if not condition:
        FAILURES.append(name)


_SEED = Path(__file__).resolve().parents[2] / "deploy" / "releases.json"
_DIGEST_A = "sha256:" + "a" * 64
_DIGEST_B = "sha256:" + "b" * 64
_DIGEST_0 = "sha256:" + "0" * 64
_TODAY = dt.date(2026, 9, 20)
_NOW = dt.datetime(2026, 9, 20, 12, 0, tzinfo=dt.timezone.utc)


def _fixture() -> dict:
    """The registry as it looked before any pipeline wrote to it: one cycle,
    one version. The scenarios below build on THIS, never on the committed
    file — the file is written by every engine release, and the first one
    (0.3.15) turned `record("0.3.15", …)` into «already recorded with another
    digest» on the very release run that ran this test. The committed file
    is still read once, to check that it validates."""
    return {
        "product": "pseudex", "schema": 1, "updated_at": "2026-09-20T00:00:00Z",
        "support": {"maintenance_months": 6, "eol_notice_days": 90},
        "cycles": [{
            "cycle": "0.3", "state": "current", "release_date": "2026-09-14",
            "eoas": None, "eol": None, "eol_announced": None,
            "latest": {"version": "0.3.14", "date": "2026-09-17", "digest": _DIGEST_0},
            "aliases": ["0.3", "0", "latest"],
        }],
        "notices": [],
    }


def _two_cycles(today: dt.date = _TODAY) -> dict:
    """0.4 current, 0.3 in maintenance with an eol announced in time."""
    doc = _fixture()
    doc = registry.record(doc, version="0.3.15", digest=_DIGEST_A, date=dt.date(2026, 9, 22), now=_NOW)
    doc = registry.record(doc, version="0.4.0", digest=_DIGEST_B, date=dt.date(2026, 10, 5), now=_NOW)
    return doc


def main() -> int:
    committed = json.loads(_SEED.read_text(encoding="utf-8"))
    check("the committed seed validates",
          registry.validate(committed, previous=None, today=dt.date.today()) == [],
          "; ".join(registry.validate(committed, previous=None, today=dt.date.today())))
    check("the fixture validates and is one version behind the scenarios",
          registry.validate(_fixture(), previous=None, today=_TODAY) == []
          and _fixture()["cycles"][0]["latest"]["version"] == "0.3.14")
    seed = _fixture()

    # ── validate: the three silent lies ──────────────────────────────────
    broken = json.loads(json.dumps(seed)); broken["cycles"][0]["latest"]["digest"] = "sha256:short"
    check("a malformed digest is refused", any("digest" in p for p in registry.validate(broken, previous=None, today=_TODAY)))

    doc = _two_cycles()
    problems = registry.validate(doc, previous=None, today=dt.date(2026, 10, 6))
    check("two cycles after a minor validate", problems == [], "; ".join(problems))
    wrong_alias = json.loads(json.dumps(doc)); wrong_alias["cycles"][1]["aliases"].append("latest")
    check("`latest` on an older cycle is refused",
          any("newest cycle only" in p or "already on cycle" in p
              for p in registry.validate(wrong_alias, previous=None, today=dt.date(2026, 10, 6))))

    late = json.loads(json.dumps(doc)); late["cycles"][1]["eol"] = "2026-10-20"  # 15 days after the announcement
    check("an eol less than 90 days after its announcement is refused",
          any("less than 90 days" in p for p in registry.validate(late, previous=None, today=dt.date(2026, 10, 6))))
    unannounced = json.loads(json.dumps(doc)); unannounced["cycles"][1]["eol_announced"] = None
    check("an eol without an announcement is refused",
          any("without eol_announced" in p for p in registry.validate(unannounced, previous=None, today=dt.date(2026, 10, 6))))

    # ── validate against the previous file: history is append-only ───────
    moved = json.loads(json.dumps(doc)); moved["cycles"][0]["latest"]["digest"] = _DIGEST_A
    check("changing the digest of a recorded version is refused",
          any("digest of 0.4.0 changed" in p for p in registry.validate(moved, previous=doc, today=dt.date(2026, 10, 6))))
    backwards = json.loads(json.dumps(doc)); backwards["cycles"][1]["latest"]["version"] = "0.3.14"; backwards["cycles"][1]["latest"]["digest"] = seed["cycles"][0]["latest"]["digest"]
    check("a latest that walks backwards is refused",
          any("went backwards" in p for p in registry.validate(backwards, previous=doc, today=dt.date(2026, 10, 6))))
    removed = json.loads(json.dumps(doc)); removed["cycles"].pop()
    check("removing a cycle is refused",
          any("removed" in p for p in registry.validate(removed, previous=doc, today=dt.date(2026, 10, 6))))

    # ── record: patch vs minor ───────────────────────────────────────────
    patched = registry.record(seed, version="0.3.15", digest=_DIGEST_A, date=dt.date(2026, 9, 22), now=_NOW)
    check("a patch moves only latest of its cycle",
          len(patched["cycles"]) == 1 and patched["cycles"][0]["latest"]["version"] == "0.3.15"
          and patched["cycles"][0]["state"] == "current" and patched["cycles"][0]["eol"] is None)
    check("a patch keeps the digest it was recorded with", patched["cycles"][0]["latest"]["digest"] == _DIGEST_A)
    check("recording the same version with another digest is refused",
          _raises(lambda: registry.record(patched, version="0.3.15", digest=_DIGEST_B, date=dt.date(2026, 9, 23), now=_NOW)))
    check("recording an older version is refused",
          _raises(lambda: registry.record(patched, version="0.3.14", digest=_DIGEST_B, date=dt.date(2026, 9, 23), now=_NOW)))

    old, new = doc["cycles"][1], doc["cycles"][0]
    check("a minor opens a new current cycle at the top",
          new["cycle"] == "0.4" and new["state"] == "current" and new["aliases"] == ["0.4", "0", "latest"])
    check("the previous cycle goes to maintenance with eol six months out, announced that day",
          old["state"] == "maintenance" and old["eoas"] == "2026-10-05" and old["eol"] == "2027-04-05"
          and old["eol_announced"] == "2026-10-05" and old["aliases"] == ["0.3"],
          json.dumps({k: old[k] for k in ("state", "eoas", "eol", "eol_announced", "aliases")}))
    check("a new cycle older than the newest is refused",
          _raises(lambda: registry.record(doc, version="0.2.9", digest=_DIGEST_A, date=dt.date(2026, 10, 6), now=_NOW)))

    # ── aliases ──────────────────────────────────────────────────────────
    check("a patch on the newest cycle moves X.Y, X and latest", registry.aliases_for(doc, "0.4.1") == ["0.4", "0", "latest"])
    check("a maintenance patch moves only X.Y", registry.aliases_for(doc, "0.3.16") == ["0.3"])
    check("a new minor takes X and latest", registry.aliases_for(doc, "0.5.0") == ["0.5", "0", "latest"])

    # ── verdict ──────────────────────────────────────────────────────────
    later = dt.date(2026, 10, 6)
    v = registry.verdict(doc, "1.0.0", later)
    check("1.0.0 (every pre-D-053 image) is read as the OLDEST cycle, not newer than newest",
          v["running_latest"] is False and v["latest_in_cycle"] == "0.3.15" and v["latest"] == "0.4.0")
    check("the floor is the oldest cycle still served", v["min_supported"] == "0.3.15")
    check("deprecated_at is the announcement day as @unix",
          v["deprecated_at"] == "@" + str(int(dt.datetime(2026, 10, 5, tzinfo=dt.timezone.utc).timestamp())), str(v["deprecated_at"]))
    check("sunset_at is the eol as an HTTP-date", v["sunset_at"] == "Mon, 05 Apr 2027 00:00:00 GMT", str(v["sunset_at"]))
    v_new = registry.verdict(doc, "0.4.0", later)
    check("the newest version runs latest and carries no dates",
          v_new["running_latest"] is True and v_new["deprecated_at"] is None and v_new["sunset_at"] is None)
    before = registry.verdict(doc, "0.3.15", dt.date(2026, 10, 4))
    check("before the announcement day there is no deprecated_at", before["deprecated_at"] is None)

    # ── notices, retracted by absence ────────────────────────────────────
    noticed = json.loads(json.dumps(doc))
    noticed["notices"] = [{"id": "2026-10-sec-01", "severity": "warning", "applies_to": ">=0.3.0 <0.3.16",
                           "text": "уязвимость", "url": "https://pseudex.ru/advisories/1"}]
    check("a notice applies by range", registry.verdict(noticed, "0.3.15", later)["notice"]["id"] == "2026-10-sec-01")
    check("a notice does not apply outside its range", registry.verdict(noticed, "0.4.0", later)["notice"] is None)
    check("a notice is gone once it is gone from the file", registry.verdict(doc, "0.3.15", later)["notice"] is None)
    check("notices validate their ranges",
          any("bad range token" in p for p in registry.validate(
              {**noticed, "notices": [{**noticed["notices"][0], "applies_to": "banana"}]}, previous=None, today=later)))

    after = dt.date(2027, 4, 6)

    # ── the calendar decides, the label catches up ───────────────────────
    # A maintenance cycle whose eol has PASSED used to make the whole file
    # invalid on that day with no edit: CI red, record refusing, the server
    # dropping the registry after a restart. The dates decide; the label lags.
    passed = registry.validate(doc, previous=None, today=dt.date(2027, 4, 6))
    check("a maintenance cycle past its eol still validates — the file does not rot on eol day",
          passed == [], "; ".join(passed))
    check("effective_state reads eol from the dates while the label still says maintenance",
          registry.effective_state(doc["cycles"][1], dt.date(2027, 4, 6)) == "eol"
          and doc["cycles"][1]["state"] == "maintenance")
    caught_up = registry.record(doc, version="0.4.3", digest=_DIGEST_B, date=dt.date(2027, 4, 6), now=_NOW)
    check("the next record writes the label the dates already meant",
          caught_up["cycles"][1]["state"] == "eol"
          and registry.validate(caught_up, previous=doc, today=dt.date(2027, 4, 6)) == [],
          "; ".join(registry.validate(caught_up, previous=doc, today=dt.date(2027, 4, 6))))
    # ── a version the registry has not heard of yet ──────────────────────
    # 0.5.0 published minutes ago, its chore(registry) not synced: it is the
    # NEWEST engine, not the oldest — reading it as the oldest cycle answered
    # 426 to the newest engine the moment any cycle was eol.
    ahead = registry.verdict(doc, "0.5.0", after)
    check("a version above every cycle is judged as the newest cycle and is not «behind»",
          ahead["running_latest"] is True and ahead["latest_in_cycle"] == "0.4.0"
          and ahead["deprecated_at"] is None, str(ahead))
    check("and is never refused, even after the oldest cycle's eol",
          registry.check(doc, "0.5.0", after) is None)
    check("1.0.0 (pre-D-053) still reads as the oldest cycle — it parses as 1.0, above everything",
          registry.verdict(doc, "1.0.0", later)["latest_in_cycle"] == "0.3.15"
          and registry.verdict(doc, "1.0.0", later)["running_latest"] is False)
    check("a version below every cycle reads as the oldest",
          registry.verdict(doc, "0.2.9", later)["latest_in_cycle"] == "0.3.15")

    # ── check: 426 only after an eol announced in time ───────────────────
    check("no refusal while the cycle is maintained", registry.check(doc, "0.3.15", later) is None)
    after = dt.date(2027, 4, 6)
    refusal = registry.check(doc, "0.3.15", after)
    check("after eol the refusal names min_supported, latest and the command",
          refusal is not None and refusal.get("error") == "unsupported_client"
          and "pseudexctl upgrade --to 0.4" in refusal["detail"] and refusal["min_supported"] == "0.4.0", json.dumps(refusal, ensure_ascii=False))
    check("1.0.0 after the oldest cycle's eol is refused too",
          (registry.check(doc, "1.0.0", after) or {}).get("error") == "unsupported_client")
    rushed = json.loads(json.dumps(doc)); rushed["cycles"][1]["eol"] = "2026-11-01"; rushed["cycles"][1]["eol_announced"] = "2026-10-25"
    verdict_late = registry.check(rushed, "0.3.15", dt.date(2026, 11, 2))
    check("an eol announced late is reported as late, NOT enforced",
          verdict_late is not None and verdict_late.get("late") is True and "error" not in verdict_late)
    check("a version in a maintained cycle whose eol has passed by less than the notice is served",
          registry.check(doc, "0.3.15", dt.date(2027, 4, 5)) is None or registry.check(doc, "0.3.15", dt.date(2027, 4, 5)).get("error") == "unsupported_client")

    # ── Watch: reload on replace, never fatal ────────────────────────────
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "releases.json"
        watch = registry.Watch(str(path))
        check("a missing file is no registry and no crash", watch.doc(later) is None and "missing" in (watch.error or ""))
        registry.dump(seed, str(path))
        check("the file is read once it exists", (watch.doc(later) or {}).get("product") == "pseudex")
        registry.dump(doc, str(path))
        check("an atomic replace is seen", len((watch.doc(later) or {}).get("cycles", [])) == 2)
        path.write_text("{not json", encoding="utf-8")
        check("a broken file yields no registry and an error, not a crash",
              watch.doc(later) is None and "unreadable" in (watch.error or ""))

    if FAILURES:
        print(f"\n{len(FAILURES)} провалено: {', '.join(FAILURES)}")
        return 1
    print("\nреестр версий: все обещания ТЗ подтверждены")
    return 0


def _raises(fn) -> bool:
    try:
        fn()
    except registry.RegistryError:
        return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
