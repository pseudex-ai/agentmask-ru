"""A surface shared by distinct values must not acquire a last-writer owner."""

import json
import re
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

import testkit
from pseudex.redact import residual_tokens, surviving_substitutes, unmask_arguments, unmask_text
from pseudex.vault import Vault


def main() -> int:
    testkit.load_dev_bundle()
    base: Vault = Vault(":memory:", "shown-ambiguity")
    view: Vault = base.for_conversation("one")
    shown: str = "восемь девятьсот семьдесят шесть тридцать три двадцать два"
    first: str = "восемь девятьсот двадцать шесть пятьдесят четыыре семьдесят восемь"
    second: str = "восемь девятьсот шестнадцать двадцать три сорок пять"
    rows: list[tuple[str, bool]] = []
    view.remember_shown(shown, first, "PHONE")
    rows.append(("unique surface restores", unmask_text(shown, view) == first))
    view.remember_shown(shown, first, "PHONE")
    rows.append(("idempotent record remains unique", unmask_text(shown, view) == first))
    view.remember_shown(shown, second, "PHONE")
    rows.append(("collision cannot select last value", unmask_text(shown, view) == shown))
    rows.append(("tool collision cannot select last value", json.loads(unmask_arguments(
        json.dumps({"phone": shown}, ensure_ascii=False), view))["phone"] == shown))
    rows.append(("collision residual is visible", shown in residual_tokens(shown, view)))
    rows.append(("leg-aware collision residual is visible", shown in surviving_substitutes(shown, shown, view, True)))
    view.remember_shown(shown, first, "PHONE")
    rows.append(("replayed first occurrence does not erase ambiguity", unmask_text(shown, view) == shown))
    view.remember_shown(shown, second, "PHONE")
    rows.append(("replayed second occurrence does not erase ambiguity", unmask_text(shown, view) == shown))
    other: Vault = base.for_conversation("two")
    other.remember_shown(shown, second, "PHONE")
    rows.append(("other conversation retains own unique surface", unmask_text(shown, other) == second))
    rows.append(("unseen conversation has no literal owner", unmask_text(shown, base.for_conversation("three")) == shown))
    # Exact rows must remain visible to the restorer even without a separately
    # minted whole token. A shown projection is evidence in its own right.
    rows.append(("unique shown residual before restoration", shown in residual_tokens(shown, other)))
    rows.append(("unique shown residual gone after restoration", not surviving_substitutes(shown, second, other, True)))
    equivalent: Vault = base.for_conversation("equivalent")
    equivalent.remember_shown("+79763322554", "+79161234567", "PHONE")
    equivalent.remember_shown("+79763322554", "8 (916) 123-45-67", "PHONE")
    rows.append(("same identity in another notation is not a collision",
                 unmask_text("+79763322554", equivalent) == "+79161234567"))
    # A TOOL'S `raw[:N]` CUT IS NOT A SECOND OWNER. The tool-result leg re-detects
    # a truncated real value and re-records the substitute for it, so a shorter
    # prefix of a value this dialogue already named arrives as a second
    # `remember_shown` under the same surface. Last-writer used to win and the
    # recorded original shrank to the cut — a later, longer cut was then no longer
    # a prefix of the evidence and escaped, and a cut whose digits parsed
    # differently even replaced the surface with a self-mapping conflict marker.
    # The authoritative identity is the LONGEST original this dialogue recorded.
    cut: Vault = base.for_conversation("truncation")
    authoritative: str = ("восемь девятьсот двадцать шесть пятьдесят четыыре семьдесят "
                          "восемь двадцать три восемсь")
    cut.remember_shown(shown, authoritative, "PHONE")
    cut.remember_shown(shown, authoritative[:85], "PHONE")
    cut.remember_shown(shown, authoritative[:86], "PHONE")
    stored: str = dict((surface, original) for surface, original, _kind in cut.shown_forms())[shown]
    rows.append(("a tool cut never shrinks the recorded identity", stored == authoritative))
    rows.append(("a tool cut is not a second owner", stored != shown))
    typed: Vault = base.for_conversation("typed")
    typed.remember_shown(shown, first, "PHONE")
    typed.remember_shown(shown, first, "SNILS")
    rows.append(("equal text with conflicting types is unresolved", unmask_text(shown, typed) == shown))
    named: Vault = base.for_conversation("equivalent-name")
    named.remember_shown("Крылов Игорь", "Иванов Пётр", "NAME")
    named.remember_shown("Крылов Игорь", "иванов петр", "NAME")
    rows.append(("case and yo variants retain the same owner",
                 unmask_text("Крылов Игорь", named) == "иванов петр"))
    named.remember_shown("Крылов Игорь", "Иванов Павел", "NAME")
    rows.append(("different given name still conflicts",
                 unmask_text("Крылов Игорь", named) == "Крылов Игорь"))
    reformatted: Vault = base.for_conversation("rewritten-conflict")
    token: str = reformatted.tokenize("+79161234567", "PHONE")
    reformatted.remember_shown(token, "+79161234567", "PHONE")
    reformatted.remember_shown(token, "+79163334455", "PHONE")
    digits: str = re.sub(r"\D", "", token)
    for surface in (digits, "8 (" + digits[1:4] + ") " + digits[4:]):
        output: str = unmask_text(surface, reformatted)
        rows.append(("rewritten conflict does not select the token owner", output == surface))
        rows.append(("rewritten conflict is visible", bool(surviving_substitutes(
            surface, output, reformatted, False))))
        rows.append(("rewritten tool conflict remains unresolved", json.loads(unmask_arguments(
            json.dumps({"phone": surface}), reformatted))["phone"] == surface))
    # POSITIVE CONTROL: the same rewrite in a dialogue with ONE owner still
    # resolves, and is not reported afterwards. The expected strings are the
    # customer's own value in the two notations, stated here rather than read
    # back off the substitute — a veto that also refused these would be a
    # regression the conflict rows alone could not see.
    clear: Vault = base.for_conversation("rewritten-clear")
    clear_shown: str = clear.tokenize("+79161234567", "PHONE")
    clear.remember_shown(clear_shown, "+79161234567", "PHONE")
    clear_digits: str = re.sub(r"\D", "", clear_shown)
    clear_grouped: str = "8 (" + clear_digits[1:4] + ") " + clear_digits[4:]
    rows.append(("unambiguous rewritten digits still restore",
                 unmask_text(clear_digits, clear) == "79161234567"))
    rows.append(("unambiguous rewritten grouping still restores",
                 unmask_text(clear_grouped, clear) == "8 (916) 1234567"))
    rows.append(("a restored rewrite is not a residual",
                 not surviving_substitutes(clear_grouped, "8 (916) 1234567", clear, False)))
    rows.append(("a restored rewrite is not reported by residual_tokens",
                 residual_tokens("79161234567", clear) == []))
    # THE SAME GUARD ON A NAME, WHICH IS ITS TYPED KEY AND NOT ITS LETTERS: a
    # person is one identity whatever the case, so `fold_key(canonicalize(…))`
    # is what has to recognise the conflict. A case-only rewrite of the
    # substitute used to select one of the two owners.
    names: Vault = base.for_conversation("rewritten-name")
    name_token: str = names.tokenize("Иванов Пётр", "NAME")
    names.remember_shown(name_token, "Иванов Пётр", "NAME")
    names.remember_shown(name_token, "Сидоров Павел", "NAME")
    shouted: str = name_token.upper()
    rows.append(("case-rewritten name conflict does not select an owner",
                 unmask_text(shouted, names) == shouted))
    rows.append(("case-rewritten name conflict is visible",
                 shouted in residual_tokens(shouted, names)))
    rows.append(("case-rewritten tool name conflict remains unresolved", json.loads(
        unmask_arguments(json.dumps({"name": shouted}, ensure_ascii=False), names))["name"] == shouted))
    places: Vault = base.for_conversation("rewritten-location")
    place_token: str = places.tokenize("Москва улица Ленина дом 14 квартира 7", "LOC")
    places.remember_shown(place_token, "Москва улица Ленина дом 14 квартира 7", "LOC")
    places.remember_shown(place_token, "Москва улица Ленина дом 15 квартира 8", "LOC")
    place_upper: str = place_token.upper()
    rows.append(("whole conflicting address cannot restore smaller parts",
                 unmask_text(place_upper, places) == place_upper))
    rows.append(("tool whole conflicting address cannot restore smaller parts", json.loads(
        unmask_arguments(json.dumps({"address": place_upper}, ensure_ascii=False), places))["address"] == place_upper))
    # Advancing the external clock makes the active replay itself trigger the
    # expiry sweep. No database rows or private sweep state are manipulated.
    later: float = time.time() + 90_000
    with patch("time.time", return_value=later):
        try:
            view.remember_shown(shown, first, "PHONE")
        except RuntimeError as error:
            rows.append((f"expired active replay does not raise: {error}", False))
        else:
            rows.append(("expired active replay does not raise", True))
        rows.append(("active replay refreshes the conflict before the sweep",
                     unmask_text(shown, view) == shown))
    with tempfile.TemporaryDirectory(prefix="shown-conflict-") as directory:
        path: str = str(Path(directory) / "vault.db")
        left: Vault = Vault(path, "persistent").for_conversation("race")
        right: Vault = Vault(path, "persistent").for_conversation("race")
        left.remember_shown(shown, first, "PHONE")
        barrier: Barrier = Barrier(2)

        def record(view_: Vault, real_: str) -> None:
            barrier.wait(timeout=10)
            view_.remember_shown(shown, real_, "PHONE")

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(record, left, first), executor.submit(record, right, second)]
            for future in futures:
                future.result(timeout=20)
        rows.append(("two independent connections preserve ambiguity", unmask_text(shown, left) == shown))
        reopened: Vault = Vault(path, "persistent").for_conversation("race")
        rows.append(("ambiguity survives reopening", unmask_text(shown, reopened) == shown))
        reopened.remember_shown(shown, first, "PHONE")
        rows.append(("replay after reopening cannot claim ownership", unmask_text(shown, reopened) == shown))
        rows.append(("reopened ambiguity remains visible", shown in residual_tokens(shown, reopened)))
    for label, ok in rows:
        if not ok:
            print("FAIL", label)
    print(f"shown_form_ambiguity: {sum(ok for _, ok in rows)}/{len(rows)}")
    return int(not all(ok for _, ok in rows))


if __name__ == "__main__":
    raise SystemExit(main())
