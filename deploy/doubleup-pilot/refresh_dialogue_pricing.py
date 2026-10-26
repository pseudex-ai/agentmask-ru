"""Refresh only authenticated pricing metadata; never call a model or enable live.

The raw response can contain provider credentials. Hash it in RAM, persist only
an explicit numeric/route whitelist, and never print response/error bodies.
"""

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import time
import urllib.request

from budget import (BudgetRefused, DIALOGUE_MODEL, Ledger, METADATA_FIELDS, OFFICIAL_POLICY,
                    PRICING_SOURCE, RATE_KEY, backup_ledger, canonical_hash, dialogue_rates, load_pricing)

HERE = Path(__file__).resolve().parent
STATE = HERE / ".state"
PROFILE = Path.home() / ".config/2up/litellm.env"


def read_private(path: Path) -> str:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor) as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.getuid():
            raise BudgetRefused("credential_profile_not_private")
        return handle.read()


def dotenv(text: str) -> dict[str, str]:
    # Keep parsing local: importing the pilot operator imports build dependencies.
    # No expansion/execution; malformed or ambiguous credentials fail closed.
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not separator or not key or key in result:
            raise BudgetRefused("credential_profile_invalid")
        if value.startswith(("'", '"')):
            if len(value) < 2 or value[-1] != value[0]:
                raise BudgetRefused("credential_profile_invalid")
            value = value[1:-1]
        result[key] = value
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise BudgetRefused("metadata_redirect_refused")


def fetch_authenticated_metadata() -> tuple[dict, str, float]:
    profile = dotenv(read_private(PROFILE))
    token = profile.get("LITELLM_TOKEN", "")
    if not token or any(char in token for char in "\r\n"):
        raise BudgetRefused("credential_profile_invalid")
    request = urllib.request.Request(PRICING_SOURCE, method="GET", headers={
        "x-litellm-api-key": token, "Accept": "application/json"})
    # Disable environment proxies and redirects: the key goes to this exact host.
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(request, timeout=30) as response:
            if response.status != 200 or response.url != PRICING_SOURCE:
                raise BudgetRefused("metadata_response_invalid")
            raw = response.read(8_000_001)
        if len(raw) > 8_000_000:
            raise BudgetRefused("metadata_response_too_large")
        return json.loads(raw), hashlib.sha256(raw).hexdigest(), time.time()
    except Exception:
        # Exception reprs may contain request objects, headers or response data.
        raise BudgetRefused("authenticated_metadata_fetch_failed") from None


def sanitize_target(row: dict) -> dict:
    info = row.get("model_info")
    if not isinstance(info, dict):
        raise BudgetRefused("target_metadata_missing")
    safe = {"model_name": DIALOGUE_MODEL, "provider": info.get("litellm_provider"),
            "mode": info.get("mode")}
    for key in ("max_input_tokens", "max_output_tokens", "max_tokens"):
        safe[key] = info.get(key)
    for key, value in info.items():
        if key.startswith(("input_cost_per_token", "output_cost_per_token")):
            if not RATE_KEY.fullmatch(key):
                if value is not None:
                    raise BudgetRefused("unknown_advertised_pricing_conflict")
                continue
            # JSON scalar rates only. No provider params, identifiers or nested data.
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float, str))):
                raise BudgetRefused("invalid_metadata_price")
            safe[key] = value
    if set(safe) - METADATA_FIELDS - {key for key in safe if RATE_KEY.fullmatch(key)}:
        raise BudgetRefused("metadata_field_not_whitelisted")
    return safe


def build_snapshot(previous: dict, response: dict, response_hash: str, fetched_at: float) -> dict:
    if previous.get("source") != PRICING_SOURCE or not isinstance(previous.get("models"), list):
        raise BudgetRefused("unexpected_pricing_source")
    if not isinstance(response, dict) or not isinstance(response.get("data"), list):
        raise BudgetRefused("metadata_response_invalid")
    targets = [sanitize_target(row) for row in response["data"]
               if isinstance(row, dict) and row.get("model_name") == DIALOGUE_MODEL]
    if not targets:
        raise BudgetRefused("target_metadata_missing")
    snapshot = copy.deepcopy(previous)
    snapshot["dialogue_pricing"] = {
        "policy": copy.deepcopy(OFFICIAL_POLICY), "policy_sha256": canonical_hash(OFFICIAL_POLICY),
        "authenticated_metadata": {"source": PRICING_SOURCE, "method": "GET", "authenticated": True,
            "fetched_at": fetched_at, "response_sha256": response_hash,
            "rows": targets, "rows_sha256": canonical_hash(targets)}}
    ip, op, context, output, _ = dialogue_rates(snapshot)
    replacements = [{"model_name": DIALOGUE_MODEL, "provider": "deepseek", "mode": "chat",
                     "input_cost_per_token": str(ip), "output_cost_per_token": str(op),
                     "max_input_tokens": context, "max_output_tokens": output, "max_tokens": output}]
    # Preserve every non-target row and top-level source field exactly. Never
    # refresh their old mtime-only permissions: the new long-context proof is
    # scoped to one exact selected model, not its aliases or experimental vision.
    snapshot["models"] = [row for row in snapshot["models"] if row.get("model_name") != DIALOGUE_MODEL] + replacements
    return snapshot


def private_artifact(path: Path, data: dict, mode=0o400) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        json.dump(data, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    path.chmod(mode)


def refresh(*, apply_holds=False) -> dict:
    pricing_path = STATE / "pricing.json"
    if pricing_path.is_symlink() or not pricing_path.is_file() or pricing_path.stat().st_mode & 0o077:
        raise BudgetRefused("pricing_snapshot_not_private")
    # The old snapshot may legitimately be expired; this operation supplies new
    # authenticated metadata. Its unrelated rows keep their original freshness.
    previous = json.loads(pricing_path.read_text())
    previous.setdefault("non_target_snapshot_mtime", pricing_path.stat().st_mtime)
    response, digest, fetched_at = fetch_authenticated_metadata()
    snapshot = build_snapshot(previous, response, digest, fetched_at)
    stamp = f"{time.time_ns()}-{os.urandom(8).hex()}"
    private_artifact(STATE / f"pricing-before-dialogue-{stamp}.json", previous)
    artifact = STATE / f"pricing-dialogue-{stamp}.json"
    private_artifact(artifact, snapshot)
    # No rename/delete: the existing bind-mounted path remains the same inode.
    descriptor = os.open(pricing_path, os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "w") as handle:
        json.dump(snapshot, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    load_pricing(pricing_path)
    result = {"selected_model": DIALOGUE_MODEL, "published_serving_alias": OFFICIAL_POLICY["published_serving_alias"],
              "input_price": snapshot["models"][-1]["input_cost_per_token"],
              "output_price": snapshot["models"][-1]["output_cost_per_token"],
              "safety_factor": 2, "pricing_artifact": artifact.name, "paid_calls": 0}
    if apply_holds:
        ledger_path = STATE / "ledger/spend.sqlite3"
        backup = backup_ledger(ledger_path)
        ledger = Ledger(ledger_path)
        details = ledger.supplement_dialogue_pricing(snapshot, backup)
        private_artifact(STATE / f"pricing-adjustment-{stamp}.json", details)
        result["adjustment"] = details
        result["ledger"] = ledger.summary()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply-local-holds", action="store_true", help="Add local accounting reserves, never paid calls")
    args = parser.parse_args()
    try:
        print(json.dumps(refresh(apply_holds=args.apply_local_holds), sort_keys=True))
    except Exception as error:
        # Only controlled reason codes, never exception values from network I/O.
        reason = str(error) if isinstance(error, BudgetRefused) else "pricing_refresh_failed"
        raise SystemExit(reason) from None


if __name__ == "__main__":
    main()
