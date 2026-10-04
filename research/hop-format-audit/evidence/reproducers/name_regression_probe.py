"""Compare the same random name substitutions across two engine snapshots."""
import argparse
import json
import random
import sys
from pathlib import Path
from unittest.mock import patch

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("root", type=Path)
args = parser.parse_args()
sys.path.insert(0, str(args.root))

import testkit
from pseudex import morph_names, translit
from pseudex.assets import ASSETS
from pseudex.detect_all import Detector
from pseudex.redact import mask_text, unmask_arguments, unmask_text
from pseudex.vault import Vault

testkit.load_dev_bundle()
detector = Detector()
ambiguous = set("юяйёщхцъ") | {"ий", "ый", "ия", "кс"}
results = []
for seed in range(12):
    rng = random.Random(seed)
    with patch("secrets.choice", side_effect=rng.choice), patch("secrets.randbelow", side_effect=rng.randrange):
        conversation = Vault(":memory:", "acme").for_conversation("c7")
        mixed = "доставка по адресу гагаринa 12 кв 5, получатель Гагарин Пётр Ильич"
        mask_text(mixed, conversation, detector.detect(mixed))
        fake = next(shown for shown, _, kind in conversation.shown_forms() if kind == "NAME")
        oblique = morph_names.inflect_person(fake, "gent", "masc")
        actual = unmask_text(f"Заказ оформлен на {oblique}.", conversation)
        results.append({"seed": seed, "probe": "case", "fake": fake, "actual": actual,
                        "ok": actual == "Заказ оформлен на Гагарина Петра Ильича."})
        for attempt in range(40):
            vault = Vault(":memory:", "acme").for_conversation("c1")
            fake = vault.tokenize("зинаида битюкова", "NAME")
            if not any(unit in ambiguous for word in fake.split() for unit in translit.units_of(word)):
                break
        else:
            raise RuntimeError(f"No unambiguous fake in seed {seed}")
        for standard in ASSETS.get().translit.tables[:2]:
            latin = " ".join(translit.apply(standard, word).upper() for word in reversed(fake.split()))
            payload = json.dumps({"contact": {"name_latin": latin}}, ensure_ascii=False)
            actual = json.loads(unmask_arguments(payload, vault))["contact"]["name_latin"]
            results.append({"seed": seed, "probe": "latin", "fake": fake, "actual": actual,
                            "ok": actual == "BITYUKOVA ZINAIDA"})
print(json.dumps(results, ensure_ascii=False, indent=2))
