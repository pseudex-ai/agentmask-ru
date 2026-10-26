"""Private local forensic intake. CLI stdout/stderr is count/code-only JSON."""

import argparse
import collections
import datetime as dt
import json
import sys
import urllib.parse
import uuid
from pathlib import Path

from .corpus import (dialog_split_proof, identified_dialog, normalize_group, normalized_strata,
                     select_groups, split_groups, summary, trace_group, unique_tool_coverage)
from .langfuse import Client, attribution, credentials, iso, utc, validate_window
from .storage import PilotError, RunStore, STATE, canonical, digest, hashed


def run_name(prefix):
    return prefix + "-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S").lower() + "-" + uuid.uuid4().hex[:10]


def window(end):
    stop = utc(end) if end else dt.datetime.now(dt.timezone.utc)
    now = dt.datetime.now(dt.timezone.utc)
    if stop > now or stop < now - dt.timedelta(days=1):
        raise PilotError("inventory_end_must_be_within_last_day")
    return stop - dt.timedelta(days=30), stop


def project_metadata(client):
    payload = client.get("/api/public/projects")
    rows = payload.get("data")
    if not isinstance(rows, list) or not all(isinstance(row, dict) and row.get("id") for row in rows):
        raise PilotError("project_metadata_invalid")
    return rows


def probe(client):
    projects = project_metadata(client)
    payload = client.get("/api/public/traces", {"limit": 1, "page": 1, "fields": "core"})
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise PilotError("trace_metadata_invalid")
    return {"auth_ok": True, "projects_visible": len(projects),
            "trace_total_reported": (payload.get("meta") or {}).get("totalItems"),
            "probe_rows": len(rows), "metadata_present": sum(bool(row.get("metadata")) for row in rows),
            "session_id_present": sum(bool(row.get("sessionId")) for row in rows),
            "trace_fields": sorted({key for row in rows for key in row}),
            "provider_calls": 0, "remote_mutations": 0}


def inventory(client, args):
    start, stop = window(args.end)
    store = RunStore(args.run_id or run_name("inventory"), True)
    projects = project_metadata(client)
    traces, completeness = client.paginated("/api/public/traces", {
        "fromTimestamp": iso(start), "toTimestamp": iso(stop), "fields": "core",
        "orderBy": "timestamp.asc"}, args.max_pages)
    validate_window(traces, start, stop)
    # Store source originals encrypted even if an older server ignores fields=core.
    store.encrypt("inventory.aesgcm", {"projects": projects, "traces": traces})
    store.encrypt("http-provenance.aesgcm", {"responses": client.response_receipts, "pages": client.pages})
    attrs = [attribution(trace) for trace in traces]
    counts = dict(collections.Counter(item["tenant_status"] for item in attrs))
    manifest = store.finish({"kind": "inventory", "created_utc": iso(dt.datetime.now(dt.timezone.utc)),
        "from_inclusive_utc": iso(start), "to_inclusive_utc": iso(stop),
        "host": client.base, "projects_visible": len(projects),
        "project_id_sha256": sorted(hashed(p["id"]) for p in projects),
        "traces": len(traces), "groups": len({trace_group(t) for t in traces}),
        "tenant_attribution_counts": counts, "source_completeness": completeness,
        "requests": client.requests, "retries": client.retries,
        "payload_redacted": False, "provider_calls": 0, "remote_mutations": 0})
    return {"run_id": store.run_id, "kind": "inventory", "traces": len(traces),
            "groups": manifest["groups"], "tenant_attribution_counts": counts,
            "source_completeness": completeness}


def observations(client, trace_id, max_pages):
    # V2 trace detail embeds V2 observations; V3 typed observations have optional
    # fields. List independently rather than trusting a possibly truncated embed.
    try:
        rows, proof = client.paginated("/api/public/observations", {"traceId": trace_id}, max_pages)
    except PilotError as exc:
        if str(exc) not in ("http_status_404", "http_status_405", "http_status_410"):
            raise
        rows, proof = client.paginated("/api/public/v2/observations", {
            "filter": json.dumps([{"type": "string", "column": "traceId", "operator": "=", "value": trace_id}]),
            "fields": "core,io,metadata,model,usage,cost,prompt"}, max_pages)
    for row in rows:
        if row.get("traceId", row.get("trace_id")) not in (None, trace_id):
            raise PilotError("observation_trace_filter_ignored")
    return rows, proof


def export(client, args):
    prior = RunStore(args.inventory, False)
    parent_manifest = prior.verify()
    if parent_manifest["kind"] != "inventory":
        raise PilotError("export_requires_inventory_run")
    if utc(parent_manifest["to_inclusive_utc"]) < dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1):
        raise PilotError("inventory_stale_reinventory")
    source = prior.read_encrypted("inventory.aesgcm")
    grouped, chosen, selection = select_groups(source["traces"], args.limit, args.seed)
    if not chosen:
        raise PilotError("empty_inventory_no_export")
    store = RunStore(args.run_id or run_name("export"), True)
    groups = []
    proofs = []
    for number, key in enumerate(chosen):
        candidate_rows = grouped[key]
        if key.startswith("session:"):
            sid = key[len("session:"):]
            rows, proof = client.paginated("/api/public/traces", {"sessionId": sid,
                "fields": "core", "orderBy": "timestamp.asc"}, args.max_pages)
            if any(row.get("sessionId") != sid for row in rows):
                raise PilotError("server_session_filter_ignored")
            if not {t["id"] for t in candidate_rows}.issubset({t["id"] for t in rows}):
                raise PilotError("session_missing_inventory_trace")
        else:
            rows = candidate_rows
            proof = {"complete": False, "reason": "no_session_id_window_only", "total": len(rows)}
        details = []
        observation_proofs = []
        for row in sorted(rows, key=lambda t: (t.get("timestamp", ""), t["id"])):
            detail = client.get("/api/public/traces/" + urllib.parse.quote(row["id"], safe=""))
            if detail.get("id") != row["id"]:
                raise PilotError("trace_detail_id_mismatch")
            if key.startswith("session:") and detail.get("sessionId") != sid:
                raise PilotError("trace_detail_session_mismatch")
            obs, obs_proof = observations(client, row["id"], args.max_pages)
            # Retain both sources verbatim. The normalizer sees both, dedups exact
            # repeated evidence, and flags conflicting call variants as ambiguous.
            detail["pilot_observations_list"] = obs
            details.append(detail)
            observation_proofs.append({"trace_id_sha256": hashed(row["id"]), **obs_proof})
        raw = {"group_id": key, "trace_metadata": rows, "trace_details": details}
        store.encrypt("source-" + str(number).zfill(4) + ".aesgcm", raw)
        group = normalize_group(key, details)
        groups.append(group)
        proofs.append({"group_sha256": hashed(key), "session_traces": proof, "observations": observation_proofs})
    actual_features = {group["group_id"]: normalized_strata(group) for group in groups}
    assignment, split = split_groups(chosen, args.seed, actual_features)
    selection["actual_split_strata"] = {arm: dict(sorted(collections.Counter(
        token for key in chosen if assignment[key] == arm for token in actual_features[key]).items()))
        for arm in ("train", "holdout")}
    selection["split_stratification"] = "actual_tenant_agent_tool_evidence_multilabel_balancing"
    for group in groups:
        group["split"] = assignment[group["group_id"]]
    store.encrypt("corpus.aesgcm", {"groups": groups, "selection": selection, "split_seed": args.seed})
    store.encrypt("http-provenance.aesgcm", {"responses": client.response_receipts, "pages": client.pages})
    complete_sessions = all(p["session_traces"]["complete"] for p in proofs)
    counts = summary(groups)
    manifest = store.finish({"kind": "export", "created_utc": iso(dt.datetime.now(dt.timezone.utc)),
        "from_inclusive_utc": parent_manifest["from_inclusive_utc"],
        "to_inclusive_utc": parent_manifest["to_inclusive_utc"], "host": client.base,
        "parent_manifest_sha256": digest(canonical(parent_manifest)),
        "parent_run_id": prior.run_id, "selection": selection, "counts": counts, "split_counts": split,
        "groups": [{"group_sha256": g["group_sha256"], "split": g["split"],
                    "trace_id_sha256": [hashed(t) for t in g["trace_ids"]],
                    "normalized_sha256": hashed(g)} for g in groups],
        "source_completeness": {"inventory": parent_manifest["source_completeness"],
            "selected_visible_sessions_complete": complete_sessions, "proofs": proofs,
            "historical_or_deleted_data_proven": False, "point_in_time_snapshot": False},
        "requests": client.requests, "retries": client.retries,
        "payload_redacted": False, "forensic_only": True, "provider_calls": 0, "remote_mutations": 0})
    return {"run_id": store.run_id, "kind": "export", "counts": counts, "split_counts": split,
            "selected_visible_sessions_complete": complete_sessions}


def reconcile(args):
    """Recover identities from full detail AFTER core-only inventory sampling.

    Source exports are immutable, including their imperfect preliminary splits.
    This produces a new lineage, quarantines identity-free traces, and never
    certifies those preliminary trace groups as independent conversations.
    """
    source = RunStore(args.source, False)
    parent = source.verify()
    if parent["kind"] != "export":
        raise PilotError("reconcile_requires_original_export")
    grouped = collections.defaultdict(list)
    seen_traces = set()
    for artifact in parent["artifacts"]:
        filename = artifact["file"]
        if not filename.startswith("source-"):
            continue
        raw = source.read_encrypted(filename)
        for trace in raw["trace_details"]:
            if trace["id"] in seen_traces:
                raise PilotError("duplicate_original_trace")
            seen_traces.add(trace["id"])
            identity = identified_dialog(trace)
            key = identity or "unscoped-trace:" + trace["id"]
            grouped[key].append(trace)
    if not grouped:
        raise PilotError("empty_original_export")
    groups = [normalize_group(key, rows) for key, rows in sorted(grouped.items())]
    for group in groups:
        group["identity_confirmed"] = all(identified_dialog(trace) is not None for trace in grouped[group["group_id"]])
    known = [g["group_id"] for g in groups if g["identity_confirmed"]]
    features = {g["group_id"]: normalized_strata(g) for g in groups if g["identity_confirmed"]}
    assignment, split_counts = split_groups(known, args.seed, features)
    for group in groups:
        group["split"] = assignment.get(group["group_id"], "unscoped")
    proof = dialog_split_proof(groups)
    split_counts["unscoped"] = proof["quarantined_unscoped_groups"]
    store = RunStore(args.run_id or run_name("reconciled"), True)
    store.encrypt("corpus.aesgcm", {"groups": groups, "split_seed": args.seed,
        "original_export_run": source.run_id, "identity_proof": proof})
    counts = summary(groups)
    coverage = unique_tool_coverage(groups)
    manifest = store.finish({"kind": "reconciled", "created_utc": iso(dt.datetime.now(dt.timezone.utc)),
        "parent_run_id": source.run_id, "parent_manifest_sha256": digest(canonical(parent)),
        "source_completeness": parent["source_completeness"], "counts": counts,
        "tool_coverage": coverage, "identity_proof": proof, "split_counts": split_counts,
        "groups": [{"group_sha256": g["group_sha256"], "split": g["split"],
            "trace_id_sha256": [hashed(tid) for tid in g["trace_ids"]], "normalized_sha256": hashed(g)} for g in groups],
        "original_payloads_unchanged": True, "preliminary_export_split_not_certified": True,
        "forensic_only": True, "provider_calls": 0, "remote_mutations": 0})
    return {"run_id": store.run_id, "kind": manifest["kind"], "counts": counts,
            "tool_coverage": coverage, "identity_proof": proof, "split_counts": split_counts}


def recorded(args):
    source = RunStore(args.source, False)
    manifest = source.verify()
    if manifest["kind"] not in ("export", "reconciled"):
        raise PilotError("recorded_requires_export_run")
    if manifest["kind"] == "reconciled":
        parent = RunStore(manifest["parent_run_id"], False).verify()
        if digest(canonical(parent)) != manifest["parent_manifest_sha256"]:
            raise PilotError("original_export_lineage_mismatch")
    corpus = source.read_encrypted("corpus.aesgcm")
    groups = corpus["groups"]
    if len({g["group_id"] for g in groups}) != len(groups):
        raise PilotError("duplicate_dialog_group")
    identity_proof = dialog_split_proof(groups)
    train = {g["group_id"] for g in groups if g["split"] == "train"}
    holdout = {g["group_id"] for g in groups if g["split"] == "holdout"}
    unscoped = {g["group_id"] for g in groups if g["split"] == "unscoped"}
    if train & holdout or train & unscoped or holdout & unscoped or len(train | holdout | unscoped) != len(groups):
        raise PilotError("whole_dialog_split_violation")
    trace_ids = [tid for group in groups for tid in group["trace_ids"]]
    if len(set(trace_ids)) != len(trace_ids):
        raise PilotError("trace_in_multiple_dialogs")
    recomputed = summary(groups)
    if recomputed != manifest["counts"]:
        raise PilotError("recorded_counts_mismatch")
    expected = {g["group_sha256"]: g["normalized_sha256"] for g in manifest["groups"]}
    if any(expected.get(g["group_sha256"]) != hashed(g) for g in groups):
        raise PilotError("normalized_hash_mismatch")
    store = RunStore(args.run_id or run_name("recorded"), True)
    result = store.finish({"kind": "recorded", "created_utc": iso(dt.datetime.now(dt.timezone.utc)),
        "source_run_id": source.run_id, "source_manifest_sha256": digest(canonical(manifest)),
        "counts": recomputed, "split_counts": {"train": len(train), "holdout": len(holdout), "unscoped": len(unscoped)},
        "identity_proof": identity_proof, "tool_coverage": unique_tool_coverage(groups),
        "validation": {"authenticated_artifacts": True, "hashes_match": True,
                       "confirmed_dialog_identity_split": True, "whole_dialog_split": not unscoped,
                       "unscoped_groups_excluded_from_comparison": True,
                       "original_payloads_encrypted": True, "is_causal_replay": False,
                       "detector_executed": False, "responses_synthesized": False},
        "source_completeness": {k: v for k, v in manifest["source_completeness"].items() if k != "proofs"},
        "provider_calls": 0, "remote_mutations": 0})
    return {"run_id": store.run_id, "kind": "recorded", "counts": recomputed,
            "split_counts": result["split_counts"], "validation": result["validation"]}


def parser():
    root = argparse.ArgumentParser(description="Local encrypted read-only Langfuse forensic intake; no model calls.")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("probe", help="Read-only auth/project/one-trace metadata counts; no artifact writes")
    inv = commands.add_parser("inventory", help="Inventory all visible traces in last 30 days")
    inv.add_argument("--end", help="UTC end timestamp, within last day; default now")
    inv.add_argument("--max-pages", type=int, default=5000)
    inv.add_argument("--run-id")
    exp = commands.add_parser("export", help="Export at most 200 original trace groups; complete session history is not guaranteed")
    exp.add_argument("--inventory", required=True)
    exp.add_argument("--limit", type=int, default=200)
    exp.add_argument("--seed", default="doubleup-local-pilot-v1")
    exp.add_argument("--max-pages", type=int, default=5000)
    exp.add_argument("--run-id")
    recon = commands.add_parser("reconcile", help="Group full-detail dialog identities; quarantine unscoped traces")
    recon.add_argument("--source", required=True)
    recon.add_argument("--run-id")
    recon.add_argument("--seed", default="doubleup-local-pilot-confirmed-dialog-v1")
    rec = commands.add_parser("recorded", aliases=["/recorded"], help="Offline integrity/count-only validation, NOT fake causal replay")
    rec.add_argument("--source", required=True)
    rec.add_argument("--run-id")
    verify = commands.add_parser("verify", help="Offline authenticated hash verification; no plaintext output")
    verify.add_argument("--source", required=True)
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "reconcile":
            result = reconcile(args)
        elif args.command in ("recorded", "/recorded"):
            result = recorded(args)
        elif args.command == "verify":
            manifest = RunStore(args.source, False).verify()
            result = {"verified": True, "run_id": args.source, "kind": manifest["kind"],
                      "artifact_count": len(manifest["artifacts"])}
        else:
            if args.command == "export" and not 1 <= args.limit <= 200:
                raise PilotError("session_limit_must_be_1_to_200")
            client = Client(credentials())
            result = probe(client) if args.command == "probe" else (
                inventory(client, args) if args.command == "inventory" else export(client, args))
        print(json.dumps(result, sort_keys=True))
        return 0
    except PilotError as exc:
        # Only our constant internal codes; no URL, path, body, or exception repr.
        print(json.dumps({"ok": False, "error_code": str(exc)}), file=sys.stderr)
        return 2
    except Exception:
        print('{"ok": false, "error_code": "unexpected_local_failure_no_details_logged"}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
