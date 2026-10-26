"""Versioned provider compatibility correction; original messages stay untouched.

DeepSeek thinking requires prior reasoning_content on tool history. Qwen traces
cannot provide that. Disable thinking for ALL arms instead of fabricating history.
V1 artifacts, its rejected request and its conservative budget reservation remain.
"""

import copy
import hashlib
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from budget import load_pricing, quote
from prepare_live import AAD, canonical, write_private

HERE = Path(__file__).resolve().parent
AAD_V2 = b"doubleup-original-live-smoke-v2"


def main():
    runtime = HERE / ".state" / "runtime"
    manifest = HERE / ".state" / "live-selection-v2.json"
    if manifest.exists():
        print(json.dumps({"prepared_existing": True, "revision": "v2"}))
        return
    key = (runtime / "live-cases.key").read_bytes()
    raw = (runtime / "live-cases.aesgcm").read_bytes()
    parent = json.loads(AESGCM(key).decrypt(raw[:12], raw[12:], AAD))
    payload = copy.deepcopy(parent)
    payload["run_id"] = "original-live-smoke-v2"
    payload["thinking_mode"] = "disabled"
    payload["compatibility_reason"] = "original_qwen_history_has_no_deepseek_reasoning_content"
    pricing = load_pricing(HERE / ".state" / "pricing.json")
    for case in payload["cases"]:
        before = canonical(case["body"]["messages"])
        case["body"]["thinking"] = {"type": "disabled"}
        if canonical(case["body"]["messages"]) != before:
            raise SystemExit("original_messages_changed")
        case["quote"] = quote(case["body"], pricing)
        case["compatibility_override"] = {"thinking": {"type": "disabled"}}
    upper = sum(case["quote"]["reserved_nano"] * 4 for case in payload["cases"])
    if upper > 10_000_000_000:
        raise SystemExit("four_arm_smoke_budget_exceeded")
    new_key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    plain = canonical(payload)
    write_private(runtime / "live-cases-v2.key", new_key)
    write_private(runtime / "live-cases-v2.aesgcm", nonce + AESGCM(new_key).encrypt(nonce, plain, AAD_V2))
    summary = {"run_id": payload["run_id"], "cases": len(payload["cases"]), "model": payload["model"],
        "thinking_mode": "disabled", "override_same_for_all_arms": True,
        "messages_unmodified": True, "tool_schemas_unmodified": True, "reasoning_history_fabricated": False,
        "parent_encrypted_case_sha256": hashlib.sha256(raw).hexdigest(),
        "encrypted_case_plaintext_sha256": hashlib.sha256(plain).hexdigest(),
        "quotes_four_arms_upper_usd": upper / 1_000_000_000,
        "diagnostic_only": True, "formal_comparative_metrics_eligible": False}
    write_private(manifest, json.dumps(summary, indent=2).encode())
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
