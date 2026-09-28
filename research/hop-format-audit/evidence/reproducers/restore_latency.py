"""Fixed-workload restore latency probe, not a production performance gate."""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from unittest.mock import patch

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("root", type=Path)
args = parser.parse_args()
sys.path.insert(0, str(args.root))

import testkit
from pseudex.detect_all import Detector
from pseudex.redact import mask_text, unmask_arguments, unmask_text
from pseudex.vault import Vault

testkit.load_dev_bundle()
detector = Detector()
vault = Vault(":memory:", "latency").for_conversation("one")
with patch("pseudex.vault._fake_phone", return_value="+79795553322"):
    source = "Телефон 8 (916) 214-88-03"
    mask_text(source, vault, detector.detect(source))
texts = ("+79795553322", "8 (979) 555-33-22", "9795553322", "+7 979 555 33 22")
payloads = tuple(json.dumps({"phone": text}) for text in texts)
result = {}
for leg in ("tool", "answer"):
    samples = []
    for index in range(1200):
        start = time.perf_counter_ns()
        if leg == "tool":
            unmask_arguments(payloads[index % 4], vault)
        else:
            unmask_text(texts[index % 4], vault)
        elapsed = (time.perf_counter_ns() - start) / 1_000_000
        if index >= 200:
            samples.append(elapsed)
    ordered = sorted(samples)
    result[leg] = {"n": len(samples), "p50_ms": statistics.median(samples),
                   "p95_ms": ordered[949], "p99_ms": ordered[989]}
print(json.dumps(result, sort_keys=True))
