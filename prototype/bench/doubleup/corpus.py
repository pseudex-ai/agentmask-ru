"""Lossless evidence normalization, conservative tool links, dialog-level splits.

All originals remain separately encrypted. Derived records reference source JSON
pointers, not a fabricated agent continuation. Missing schemas/call IDs/results
are evidence gaps, never synthesized from tool names or observed arguments.
"""

import collections
import json
import math

from .langfuse import attribution, trace_group
from .storage import PilotError, canonical, hashed


def walk(value, pointer=""):
    """Inspect recognized JSON structures, including JSON-serialized observations."""
    if isinstance(value, str) and value.lstrip().startswith(("{", "[")):
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, RecursionError):
            return
        yield from walk(parsed, pointer + "/@json")
    elif isinstance(value, dict):
        yield value, pointer
        for key, item in value.items():
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            yield from walk(item, pointer + "/" + escaped)
    elif isinstance(value, list):
        yield value, pointer
        for index, item in enumerate(value):
            yield from walk(item, pointer + "/" + str(index))


def tool_hints(trace):
    """Only explicit tool metadata/calls, never guess that any named SPAN is a tool."""
    names = set()
    for node, _ in walk({"metadata": trace.get("metadata"),
                         "observations": trace.get("observations", [])}):
        if not isinstance(node, dict):
            continue
        if str(node.get("type", "")).upper() in ("TOOL", "TOOL_CALL") and node.get("name"):
            names.add(str(node["name"]))
        if isinstance(node.get("tool_name"), str):
            names.add(node["tool_name"])
        for call in node.get("tool_calls", []) if isinstance(node.get("tool_calls"), list) else []:
            if isinstance(call, dict) and isinstance(call.get("function"), dict) and call["function"].get("name"):
                names.add(call["function"]["name"])
    return sorted(names)


def strata(trace):
    attr = attribution(trace)
    tokens = {"tenant:" + (hashed(attr["tenant_id"]) if attr["tenant_id"] else attr["tenant_status"])}
    tokens |= {"agent:" + hashed(agent) for agent in attr["agent_evidence"]}
    if not attr["agent_evidence"]:
        # Trace name is only an agent proxy, never claimed as an assistant id.
        tokens.add("agent-proxy:" + hashed(trace.get("name")))
    tools = tool_hints(trace)
    tokens |= {"tool:" + hashed(tool) for tool in tools} if tools else {"tool:unknown"}
    return tokens


def select_groups(traces, limit, seed):
    if not 1 <= limit <= 200:
        raise PilotError("session_limit_must_be_1_to_200")
    grouped = collections.defaultdict(list)
    for trace in traces:
        grouped[trace_group(trace)].append(trace)
    features = {key: set().union(*(strata(t) for t in rows)) for key, rows in grouped.items()}
    frequency = collections.Counter(token for tokens in features.values() for token in tokens)
    coverage = collections.Counter()
    remaining = set(grouped)
    chosen = []
    # Greedy inverse-frequency coverage with diminishing return, deterministic ties.
    # It oversamples rare strata intentionally: a pilot, NOT an unbiased prevalence estimate.
    while remaining and len(chosen) < limit:
        def priority(key):
            score = sum(1 / (frequency[t] * (1 + coverage[t])) for t in features[key])
            return (-score, hashed([seed, key]))
        key = min(remaining, key=priority)
        chosen.append(key)
        coverage.update(features[key])
        remaining.remove(key)
    return grouped, chosen, {"candidate_groups": len(grouped), "selected_groups": len(chosen),
        "available_strata": dict(sorted(frequency.items())), "selected_strata": dict(sorted(coverage.items())),
        "tool_stratification": "explicit_metadata_hints_only_unknown_retained",
        "agent_fallback": "trace_name_proxy_not_confirmed_agent_id"}


def snapshots(sources):
    collected = {}
    for source, value in sources:
        for node, pointer in walk(value):
            if not isinstance(node, list) or not node or not all(
                isinstance(message, dict) and isinstance(message.get("role"), str) for message in node):
                continue
            key = hashed(node)
            if key not in collected:
                collected[key] = {"sha256": key, "messages": node, "provenance": []}
            collected[key]["provenance"].append({"source": source, "pointer": pointer})
    rows = list(collected.values())
    maximal = []
    superseded = []
    for row in rows:
        supersets = [other for other in rows if len(other["messages"]) > len(row["messages"])
                     and other["messages"][:len(row["messages"])] == row["messages"]]
        if supersets:
            superseded.append({"sha256": row["sha256"], "provenance": row["provenance"],
                               "prefix_of": sorted(other["sha256"] for other in supersets)})
        else:
            maximal.append(row)
    # Position-sensitive dedup: identical repeated messages at two positions remain
    # two occurrences; shared prefixes across growing/branched snapshots count once.
    unique = {(index, hashed(message)) for row in rows for index, message in enumerate(row["messages"])}
    return {"maximal": sorted(maximal, key=lambda row: row["sha256"]), "superseded": superseded,
            "unique_message_occurrences": len(unique), "distinct_snapshots": len(rows),
            "snapshot_occurrences": sum(len(row["provenance"]) for row in rows)}


def tools(sources):
    schemas, calls, results, unlinked = {}, {}, {}, []

    def add(target, identity, record, source, pointer):
        key = hashed([identity, record])
        if key not in target:
            target[key] = dict(record, provenance=[])
        target[key]["provenance"].append({"source": source, "pointer": pointer})

    for source, value in sources:
        for node, pointer in walk(value):
            if not isinstance(node, dict):
                continue
            # These are schema declarations, not inferred schemas from arguments.
            for field in ("tools", "functions"):
                declarations = node.get(field)
                if not isinstance(declarations, list):
                    continue
                for index, declaration in enumerate(declarations):
                    if not isinstance(declaration, dict):
                        continue
                    function = declaration.get("function", declaration)
                    if not isinstance(function, dict) or not function.get("name"):
                        continue
                    if "parameters" not in function and "inputSchema" not in function and "input_schema" not in function:
                        continue
                    add(schemas, hashed(declaration), {"name": function["name"], "schema": declaration,
                        "schema_sha256": hashed(declaration)}, source, pointer + "/" + field + "/" + str(index))
            call_list = node.get("tool_calls")
            if isinstance(call_list, list):
                for index, call in enumerate(call_list):
                    if not isinstance(call, dict):
                        continue
                    function = call.get("function", call)
                    if not isinstance(function, dict):
                        continue
                    add(calls, call.get("id"), {"call_id": call.get("id"), "name": function.get("name"),
                        "arguments": function.get("arguments", function.get("args")),
                        "arguments_present": "arguments" in function or "args" in function},
                        source, pointer + "/tool_calls/" + str(index))
            if node.get("type") == "tool_use":
                add(calls, node.get("id"), {"call_id": node.get("id"), "name": node.get("name"),
                    "arguments": node.get("input"), "arguments_present": "input" in node}, source, pointer)
            if node.get("role") == "tool" or node.get("type") == "tool_result":
                call_id = node.get("tool_call_id", node.get("tool_use_id"))
                add(results, call_id, {"call_id": call_id, "result": node.get("content"),
                                      "result_present": "content" in node}, source, pointer)
            # V3 typed tool observation, or V2 span with explicit call-id metadata.
            metadata = node.get("metadata") or {}
            if not isinstance(metadata, dict):
                metadata = {}
            call_id = node.get("toolCallId", node.get("tool_call_id", metadata.get("tool_call_id", metadata.get("toolCallId"))))
            is_tool = str(node.get("type", "")).upper() in ("TOOL", "TOOL_CALL")
            if is_tool or (call_id and "startTime" in node):
                if call_id:
                    add(calls, call_id, {"call_id": call_id, "name": node.get("name"),
                        "arguments": node.get("input"), "arguments_present": "input" in node}, source, pointer)
                    if "output" in node:
                        add(results, call_id, {"call_id": call_id, "result": node["output"],
                                             "result_present": True}, source, pointer)
                else:
                    unlinked.append({"name": node.get("name"), "reason": "missing_call_id",
                                     "source": source, "pointer": pointer})
    call_rows = list(calls.values())
    result_rows = list(results.values())
    for call in call_rows:
        cid = call["call_id"]
        matching_calls = [c for c in call_rows if cid and c["call_id"] == cid]
        matching_results = [r for r in result_rows if cid and r["call_id"] == cid]
        call["link_status"] = ("missing_call_id" if not cid else "ambiguous_call_id" if len(matching_calls) > 1
                               else "ambiguous_result" if len(matching_results) > 1
                               else "linked" if matching_results else "missing_result")
        call["result_sha256"] = hashed(matching_results[0]["result"]) if call["link_status"] == "linked" else None
        matching_schemas = [s["schema_sha256"] for s in schemas.values() if s["name"] == call["name"]]
        call["schema_status"] = "present" if matching_schemas else "missing"
        call["schema_sha256_candidates"] = sorted(set(matching_schemas))
    return {"schemas": list(schemas.values()), "calls": call_rows, "results": result_rows,
            "unlinked_tool_observations": unlinked,
            "orphan_results": sum(not r["call_id"] or not any(c["call_id"] == r["call_id"] for c in call_rows)
                                  for r in result_rows)}


def normalize_group(key, traces):
    sources = []
    for trace in traces:
        tid = trace["id"]
        sources.append(("trace:" + tid, trace))
    attr = [attribution(t) for t in traces]
    tenants = {tenant for item in attr for tenant in item["tenant_evidence"]}
    status = "ambiguous" if len(tenants) > 1 or any(a["tenant_status"] == "ambiguous" for a in attr) else (
        "attributed" if len(tenants) == 1 and all(a["tenant_status"] == "attributed" for a in attr) else "unknown")
    dialog = snapshots(sources)
    tool_data = tools(sources)
    return {"group_id": key, "group_sha256": hashed(key), "trace_ids": [t["id"] for t in traces],
            "tenant_status": status, "attribution": attr, "dialog": dialog, "tools": tool_data,
            "is_causal_replay": False, "original_content": True,
            "scope": "session_all_visible_traces" if key.startswith("session:") else "window_only_no_session_id"}


def normalized_strata(group):
    """Actual exported tenant/agent/tool evidence, not trace-name guesses."""
    tokens = {"tenant-status:" + group["tenant_status"]}
    for attr in group["attribution"]:
        tokens |= {"tenant:" + hashed(tenant) for tenant in attr["tenant_evidence"]}
        tokens |= {"agent:" + hashed(agent) for agent in attr["agent_evidence"]}
    names = {call["name"] for call in group["tools"]["calls"] if call["name"]}
    names |= {row["name"] for row in group["tools"]["unlinked_tool_observations"] if row["name"]}
    tokens |= {"tool:" + hashed(name) for name in names} if names else {"tool:unknown"}
    if not any(token.startswith("agent:") for token in tokens):
        tokens.add("agent:unknown")
    return tokens


def split_groups(groups, seed, features=None):
    """Whole dialogs, exact 80/20 counts, greedy multilabel stratum balancing.

    Singletons cannot occur in both arms; balance never duplicates a dialog to
    pretend otherwise. Hashed token coverage is published for each arm.
    """
    if not groups:
        return {}, {"train": 0, "holdout": 0}
    ordered = sorted(groups, key=lambda key: hashed(["split", seed, key]))
    train_count = math.floor(len(ordered) * .8)
    holdout_count = len(ordered) - train_count
    if features is None:
        features = {key: set() for key in ordered}
    frequency = collections.Counter(token for key in ordered for token in features[key])
    observed = collections.Counter()
    held = set()
    for _ in range(holdout_count):
        def priority(key):
            improvement = sum((2 * (frequency[token] * holdout_count / len(ordered) - observed[token]) - 1)
                              / frequency[token] for token in features[key])
            return (-improvement, hashed(["split", seed, key]))
        key = min((key for key in ordered if key not in held), key=priority)
        held.add(key)
        observed.update(features[key])
    assignment = {key: "holdout" if key in held else "train" for key in ordered}
    return assignment, {"train": train_count, "holdout": holdout_count}


def identified_dialog(trace):
    """An observed identity, never a userId or content-similarity guess."""
    attr = attribution(trace)
    if attr["tenant_status"] != "attributed":
        return None
    dialogs = sorted(attr["dialog_evidence"])
    if len(dialogs) == 1:
        return "dialog:" + hashed([attr["tenant_id"], dialogs[0]])
    session = trace.get("sessionId")
    if isinstance(session, str) and session and not dialogs:
        return "session:" + hashed([attr["tenant_id"], session])
    return None


def identity_of_group(group):
    tenants = {tenant for attr in group["attribution"] for tenant in attr["tenant_evidence"]}
    dialogs = {dialog for attr in group["attribution"] for dialog in attr["dialog_evidence"]}
    if group["tenant_status"] != "attributed" or len(tenants) != 1:
        return None
    if len(dialogs) == 1:
        return "dialog:" + hashed([next(iter(tenants)), next(iter(dialogs))])
    # Original exports have a literal server session ID; reconciled IDs are
    # already tenant-bound hashes. Both require explicit unique tenant evidence.
    if not dialogs and group["group_id"].startswith("session:"):
        if group.get("identity_confirmed") is True:
            return group["group_id"]
        if group.get("scope") == "session_all_visible_traces":
            return "session:" + hashed([next(iter(tenants)), group["group_id"][len("session:"):]])
    return None


def dialog_split_proof(groups):
    seen = collections.defaultdict(set)
    identified = 0
    quarantined = 0
    for group in groups:
        identity = identity_of_group(group)
        split = group["split"]
        if split not in ("train", "holdout", "unscoped"):
            raise PilotError("invalid_dialog_split")
        if identity is None:
            if split != "unscoped":
                raise PilotError("unidentified_dialog_in_comparative_split")
            quarantined += 1
            continue
        if split == "unscoped":
            quarantined += 1
            continue
        seen[identity].add(split)
        identified += 1
    if any(len(splits) > 1 for splits in seen.values()):
        raise PilotError("dialog_identity_cross_split")
    if identified != len(seen):
        raise PilotError("same_dialog_in_multiple_groups")
    return {"confirmed_dialog_groups": identified, "quarantined_unscoped_groups": quarantined,
            "known_dialog_cross_split": 0, "comparative_groups_have_confirmed_identity": True,
            "whole_history_proven": False}


def unique_tool_coverage(groups):
    names = {row["name"] for group in groups for row in group["tools"]["schemas"]}
    variants = {row["schema_sha256"] for group in groups for row in group["tools"]["schemas"]}
    return {"distinct_schema_names": len(names), "distinct_schema_variants": len(variants),
            "schema_occurrences": sum(len(group["tools"]["schemas"]) for group in groups),
            "schema_occurrences_are_not_unique_tools": True}


def summary(groups):
    counts = collections.Counter()
    for group in groups:
        counts["groups"] += 1
        counts["traces"] += len(group["trace_ids"])
        counts["tenant_" + group["tenant_status"]] += 1
        counts["maximal_dialog_snapshots"] += len(group["dialog"]["maximal"])
        counts["prefix_snapshots_removed"] += len(group["dialog"]["superseded"])
        counts["unique_message_occurrences"] += group["dialog"]["unique_message_occurrences"]
        counts["snapshot_occurrences"] += group["dialog"]["snapshot_occurrences"]
        counts["exact_tool_schemas"] += len(group["tools"]["schemas"])
        counts["tool_calls"] += len(group["tools"]["calls"])
        counts["tool_results"] += len(group["tools"]["results"])
        counts["unlinked_tool_observations"] += len(group["tools"]["unlinked_tool_observations"])
        counts["orphan_results"] += group["tools"]["orphan_results"]
        counts["window_only_no_session_id"] += group["scope"] == "window_only_no_session_id"
        for call in group["tools"]["calls"]:
            counts["call_" + call["link_status"]] += 1
            counts["schema_" + call["schema_status"]] += 1
    return dict(sorted(counts.items()))
