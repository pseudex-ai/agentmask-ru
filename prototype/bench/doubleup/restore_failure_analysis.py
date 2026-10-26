"""Read-only, zero-provider-call diagnosis of an encrypted restoration failure.

Actual values never cross stdout or a plaintext file. Optional evidence uses the
existing authenticated encrypted RunStore. No live masking, reveal or tool calls.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from collections import Counter

from .storage import RunStore

SOURCE_RUN = "pseudex-full-dialogue-restore-failure-v1"
SOURCE_ARTIFACT = "failed-attempt-and-local-restore.aesgcm"

SIDECAR = "obscura-doubleup-pilot-sidecar-1"


def vault_snapshot(tenant):
    # This process opens the existing SQLCipher volume mode=ro. Neither key nor
    # plaintext reaches disk or the terminal; stdout is captured directly in RAM.
    code = r'''
import json, os, sys
from pseudex.sqlite_setup import connect_readonly, VAULT_STORE
try:
    tenant = json.load(sys.stdin)["tenant"]
    path = os.path.join(os.environ.get("PSEUDEX_DB_DIR", "/data"), "vault.db")
    conn = connect_readonly(path, VAULT_STORE)
    conn.execute("PRAGMA query_only=ON")
    conn.execute("BEGIN")
    out = {"tables": {}}
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
    for (name,) in tables:
        if not name.replace("_", "").isalnum():
            raise ValueError("unsafe_table")
        columns = [row[1] for row in conn.execute('PRAGMA table_info("' + name + '")')]
        if "customer" not in columns:
            continue
        rows = conn.execute('SELECT * FROM "' + name + '" WHERE customer=?', (tenant,)).fetchall()
        out["tables"][name] = {"columns": columns, "rows": rows}
    conn.rollback()
    conn.close()
    print(json.dumps(out))
except Exception as exc:
    print(json.dumps({"error_class": type(exc).__name__}))
    sys.exit(2)
'''
    result = subprocess.run(["docker", "exec", "-i", SIDECAR, "python", "-c", code],
                            input=json.dumps({"tenant": tenant}), capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("private_vault_read_failed")
    return json.loads(result.stdout)


def replay_capture_parity(evidence):
    attempt = evidence["attempt"]
    payload = {"org_id": attempt["tenant_id"], "conversation_id": attempt["thread_id"],
               "agent_id": attempt["agent_id"], "pseudonym_scope": "conversation",
               "request_id": "restore-failure-readonly-diagnosis", "response": attempt["model_response"]}
    code = r'''
import httpx, json, os, sys
from urllib.parse import urlsplit
try:
    body = json.load(sys.stdin)
    base = os.environ["PSEUDEX_BASE_URL"].rstrip("/")
    u = urlsplit(base)
    if u.scheme != "http" or u.hostname != "sidecar" or u.port != 8000 or u.path:
        raise ValueError("nonlocal_sidecar_refused")
    token = os.environ["PSEUDEX_GATEWAY_TOKEN"]
    out = []
    with httpx.Client(timeout=30, follow_redirects=False, trust_env=False) as client:
        for flag in (False, True):
            response = client.post(base + "/unmask", json={**body, "inspection": flag},
                                   headers={"Authorization": "Bearer " + token})
            out.append({"status": response.status_code, "body": response.json()})
    print(json.dumps(out))
except Exception as exc:
    print(json.dumps({"error_class": type(exc).__name__}))
    sys.exit(2)
'''
    result = subprocess.run(["docker", "exec", "-i", "obscura-doubleup-pilot-graph_server-1", "python", "-c", code],
                            input=json.dumps(payload), capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("private_capture_replay_failed")
    replies = json.loads(result.stdout)
    plain, capture = [r["body"] for r in replies]
    report = {"statuses": [r["status"] for r in replies],
              "responses_equal": plain.get("response") == capture.get("response"),
              "residuals_equal": plain.get("residual_tokens", []) == capture.get("residual_tokens", []),
              "residual_counts": [len(r["body"].get("residual_tokens", [])) for r in replies],
              "semantic_complete": capture.get("inspection", {}).get("semantic_complete"),
              "restore_operations": len(capture.get("inspection", {}).get("replacements", []))}
    return report, replies


def baseline_module():
    # Isolate BOTH committed modules in RAM. Loading only redact while sharing a
    # dirty Vault would silently turn a concurrent core fix into a false baseline.
    import sys
    import types
    from pathlib import Path
    root = Path(__file__).resolve().parents[3]

    def load(stem):
        result = subprocess.run(["git", "show", "HEAD:prototype/pseudex/" + stem + ".py"],
                                cwd=root, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError("baseline_read_failed")
        module = types.ModuleType("pseudex._restore_analysis_baseline_" + stem)
        sys.modules[module.__name__] = module
        exec(compile(result.stdout, "<HEAD:pseudex/" + stem + ".py>", "exec"), module.__dict__)
        return module, ast.parse(result.stdout)

    vault, _ = load("vault")
    module, tree = load("redact")
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "pseudex.vault":
            for name in node.names:
                setattr(module, name.asname or name.name, getattr(vault, name.name))
    module._baseline_vault = vault
    return module


def classify_vault(evidence, snapshot):
    from testkit import load_dev_bundle
    load_dev_bundle()
    from pseudex.vault import Vault, token_re
    from pseudex import redact, ru_pii_v6, translit
    attempt = evidence["attempt"]
    def snapshot_view(cls):
        base = cls(":memory:", attempt["tenant_id"])
        for name, table in snapshot["tables"].items():
            quoted = ",".join('"' + c + '"' for c in table["columns"])
            marks = ",".join("?" for _ in table["columns"])
            base._conn.executemany('INSERT INTO "' + name + '" (' + quoted + ') VALUES (' + marks + ')', table["rows"])
        base._conn.commit()
        base._conn.execute("PRAGMA query_only=ON")
        return base.for_conversation(attempt["thread_id"])

    vault = snapshot_view(Vault)
    raw = attempt["model_response"]["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
    after = evidence["sidecar_body"]["response"]["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
    baseline = baseline_module()
    baseline_vault = snapshot_view(baseline._baseline_vault.Vault)
    baseline_call = baseline._argument_view(baseline._call_texts(raw), baseline_vault)
    asked = redact._written_candidates(raw, True).standing_in(after)
    call = redact._argument_view(redact._call_texts(raw), vault)
    report = {"table_counts": {n: len(t["rows"]) for n, t in snapshot["tables"].items()},
              "residual_reproduced": redact.surviving_substitutes(raw, after, vault, True) == evidence["sidecar_body"].get("residual_tokens", []),
              "raw_equals_restored": raw == after, "candidates": [],
              "baseline_residual_reproduced": baseline.surviving_substitutes(raw, after, baseline_vault, True) == evidence["sidecar_body"].get("residual_tokens", []),
              "baseline_restore_equals_current": baseline.unmask_arguments(raw, baseline_vault) == redact.unmask_arguments(raw, vault)}
    # Same symbol table, fresh method only: a diagnostic hypothesis, NEVER an
    # operational waiver and never passed to a live sidecar or tool executor.
    from unittest.mock import patch
    from test_restore_code_residual import trial_name_grammar
    with patch.object(Vault, "residual_of", trial_name_grammar(Vault.residual_of)):
        trial_out = redact.unmask_arguments(raw, vault)
        trial_residual = redact.surviving_substitutes(raw, trial_out, vault, True)
    report["ram_only_hypothesis"] = {
        "response_unchanged": trial_out == after,
        "residual_count": len(trial_residual), "operational_waiver": False}
    report["baseline_revision"] = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    leaf_thread = json.loads(raw).get("thread_id", "")
    report["thread_leaf"] = {
        "uuid_shape": bool(re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", leaf_thread)),
        "length": len(leaf_thread),
        "source_request_occurrences": sum(t.count(leaf_thread) for _, t in string_nodes(attempt["source_request"])),
        "model_request_occurrences": sum(t.count(leaf_thread) for _, t in string_nodes(attempt["model_request"])),
        "source_messages_occurrences": sum(t.count(leaf_thread) for _, t in string_nodes(attempt["source_messages"])),
        "whole_exact_token": bool(call.detokenize_many({leaf_thread})),
        "is_runtime_thread": leaf_thread == attempt["thread_id"],
    }
    for value in evidence["sidecar_body"].get("residual_tokens", []):
        digits = "".join(c for c in value if c.isdigit())
        fold_key = translit.fold(value)
        part_rows = call._conn.execute(
            "SELECT p.token FROM token_parts p JOIN tokens t ON p.customer=t.customer AND p.token=t.token WHERE p.customer=? AND p.part=? AND t.entity_type='NAME'",
            (attempt["tenant_id"], fold_key)).fetchall()
        owner = call.residual_of(value)
        baseline_owner = baseline_call.residual_of(value)
        forms = vault.shown_forms()
        report["name_lookup"] = {
            "fold_key_length": len(fold_key), "fold_equals_letters_only": fold_key == translit.fold("".join(c for c in value if c.isalpha())),
            "matching_name_tokens": len(part_rows),
            "owner_shape": shape(owner) if owner is not None else None,
            "owner_words": len(owner.split()) if owner else 0,
            "shown_conflict_branch": redact._conflicts_with(value, redact._conflict_keys(forms)),
            "shown_exact_branch": value in redact._shown_surfaces(raw, forms),
            "owner_is_shown": any(owner == shown for shown, _, _ in forms),
            "baseline_owner_shape": shape(baseline_owner) if baseline_owner is not None else None,
            "baseline_owner_is_shown": any(baseline_owner == shown for shown, _, _ in forms),
        }
        owned = call.detokenize_many({value})
        origins = []
        for label, pattern in [("token_re", token_re()), ("utility", ru_pii_v6.UTILITY_TOKEN_RE),
                               ("finance", ru_pii_v6.FINANCE_TOKEN_RE), ("num_run", redact._NUM_RUN)]:
            if any(m.group().strip() == value for m in pattern.finditer(raw)):
                origins.append(label)
        rows = snapshot["tables"]["tokens"]
        ix = {c: i for i, c in enumerate(rows["columns"])}
        digit_owner_types = Counter()
        exact_owner_types = Counter()
        for row in rows["rows"]:
            if value == row[ix["token"]]:
                exact_owner_types[row[ix["entity_type"]]] += 1
            if digits and digits in "".join(c for c in row[ix["token"]] if c.isdigit()):
                digit_owner_types[row[ix["entity_type"]]] += 1
        report["candidates"].append({"shape": shape(value), "origins": origins,
            "asked_groups": [name for name in ("named", "words") if value in getattr(asked, name)],
            "known": value in owned, "name_residual_owner": call.residual_of(value) is not None,
            "pieces_branch": value in redact._pieces_of_ours(asked, set(), call),
            "finance_shape_labels": [label for label, pattern in ru_pii_v6.FINANCE_SHAPES.items() if pattern.fullmatch(value)],
            "argument_uuid_segment": value in leaf_thread.split("-"),
            "whole_digit_floor": redact._still_a_whole_value(value),
            "digit_fragment_is_ours": call.digit_fragment_is_ours(digits),
            "digit_count": len(digits), "exact_owner_types": dict(exact_owner_types),
            "digit_owner_types": dict(digit_owner_types),
            "runtime_uuid_segment": value in attempt["thread_id"].split("-"),
        })
    return report

def shape(value: str) -> str:
    return "".join("D" if c.isdigit() else "A" if c.isalpha() else c
                   if c in ".-_/+ :" else "P" for c in value)


def string_nodes(value, path=""):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from string_nodes(child, path + "/" + str(key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from string_nodes(child, path + "/" + str(index))


def private_summary(evidence):
    residuals = evidence["sidecar_body"].get("residual_tokens", [])
    attempt = evidence["attempt"]
    raw = attempt["model_response"]
    restored = evidence["sidecar_body"]["response"]
    toolcall = raw["choices"][0]["message"]["tool_calls"][0]
    safe_id = lambda x: x if isinstance(x, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", x) else "nonstandard-id-redacted"
    summary = {
        "attempt_id": safe_id(attempt["attempt_id"]),
        "response_id": safe_id(raw.get("id")),
        "tool_call_id": safe_id(toolcall.get("id")),
        "tool_function": safe_id(toolcall.get("function", {}).get("name")),
        "evidence_keys": sorted(evidence),
        "attempt_keys": sorted(attempt),
        "residual_count": len(residuals),
        "sidecar_status": evidence["sidecar_status"],
        "residuals": [],
    }
    private = []
    for value in residuals:
        locations = []
        for path, text in string_nodes(raw):
            if value not in text:
                continue
            item = {"path": path, "occurrences": text.count(value)}
            try:
                args = json.loads(text)
            except (ValueError, TypeError):
                args = None
            if args is not None:
                item["json_valid"] = True
                item["leaf_hits"] = []
                for leaf_path, leaf in string_nodes(args):
                    if value in leaf:
                        hit = {"leaf_path": leaf_path, "occurrences": leaf.count(value)}
                        try:
                            tree = ast.parse(leaf)
                        except (SyntaxError, ValueError):
                            tree = None
                        hit["python_parseable"] = tree is not None
                        if tree is not None:
                            kinds = Counter()
                            for node in ast.walk(tree):
                                if isinstance(node, ast.Constant) and value in (ast.get_source_segment(leaf, node) or ""):
                                    kinds[type(node.value).__name__] += 1
                            hit["python_constant_kinds"] = dict(kinds)
                        item["leaf_hits"].append(hit)
            locations.append(item)
        summary["residuals"].append({
            "length": len(value), "shape": shape(value),
            "ascii": value.isascii(), "alpha": value.isalpha(),
            "digits": value.isdigit(), "raw_locations": locations,
            "restored_occurrences": sum(t.count(value) for _, t in string_nodes(restored)),
        })
        private.append({"value": value, "raw_locations": locations})
    return summary, private


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-run")
    parser.add_argument("--vault", action="store_true")
    parser.add_argument("--capture-parity", action="store_true")
    parser.add_argument("--snapshot-run", help="reuse encrypted snapshot instead of opening live vault")
    args = parser.parse_args()
    source = RunStore(SOURCE_RUN, False)
    evidence = source.read_encrypted(SOURCE_ARTIFACT)
    summary, private = private_summary(evidence)
    snapshot = None
    replies = None
    if args.vault and args.snapshot_run:
        raise ValueError("choose_live_or_archived_snapshot")
    if args.snapshot_run:
        saved = RunStore(args.snapshot_run, False)
        saved.verify()
        archived = saved.read_encrypted("private-analysis.aesgcm")
        snapshot = archived["vault_snapshot"]
        replies = archived.get("local_unmask_replies")
    elif args.vault:
        snapshot = vault_snapshot(evidence["attempt"]["tenant_id"])
    if snapshot is not None:
        summary["vault"] = classify_vault(evidence, snapshot)
    if replies is not None:
        summary["archived_capture_parity"] = (archived["summary"].get("capture_parity")
                                                or archived["summary"].get("archived_capture_parity"))
    if args.capture_parity:
        summary["capture_parity"], replies = replay_capture_parity(evidence)
    if args.evidence_run:
        target = RunStore(args.evidence_run, True)
        target.encrypt("private-analysis.aesgcm", {"summary": summary, "private": private,
                                                   "vault_snapshot": snapshot,
                                                   "local_unmask_replies": replies})
        target.finish({"purpose": "read-only-restoration-diagnosis", "provider_calls": 0,
                       "residual_count": summary["residual_count"]})
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Exception messages may contain real strings; expose only the class.
        print(json.dumps({"error_class": type(exc).__name__}))
        raise SystemExit(2) from None
