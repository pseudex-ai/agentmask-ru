"""A spoken date keeps the current speaker's day case across both legs."""

import json
from unittest.mock import patch

import testkit
from pseudex.detect import Span
from pseudex.redact import mask_text, unmask_arguments, unmask_text
from pseudex.vault import Vault


def main() -> int:
    testkit.load_dev_bundle()
    original: str = "четвёртое августа девяносто седьмого года"
    vault: Vault = Vault(":memory:", "spoken-date-form").for_conversation("one")
    with patch("pseudex.vault._fake_date", return_value="13.03.1997"):
        shown: str = mask_text(original, vault, [Span(0, len(original), "DOB", original)])
    rows: list[tuple[str, str, str]] = [
        ("IN nominative day", shown, "тринадцатое марта девяносто седьмого года"),
    ]
    examples: tuple[tuple[str, str], ...] = (
        ("тринадцатое марта девяносто седьмого года", original),
        ("тринадцатого марта девяносто седьмого года", "четвёртого августа девяносто седьмого года"),
        ("1997-03-13", "1997-08-04"),
    )
    for written, expected in examples:
        arguments: str = json.dumps({"birth_date": written}, ensure_ascii=False)
        restored: str = json.loads(unmask_arguments(arguments, vault))["birth_date"]
        rows.append(("tool " + written, restored, expected))
        rows.append(("answer " + written, unmask_text(written, vault), expected))
    failures: list[tuple[str, str, str]] = [row for row in rows if row[1] != row[2]]
    for label, actual, expected in failures:
        print(f"FAIL {label}: {actual!r} != {expected!r}")
    print(f"spoken_date_form: {len(rows) - len(failures)}/{len(rows)}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
