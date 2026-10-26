"""Deterministic LOCAL tool adapters, not historical-answer replay.

There is deliberately no network, shell, eval, subprocess, provider, backend
registry import or executor callback here. Call results are recomputed from an
arm-owned resource clone and strict source-declared contracts. The lead runner
must feed these NEW results to its NEXT generation; original tool/assistant
messages are evidence/resource provenance, never a dispatch fallback.

Resource dictionaries and successful return values can contain customer data:
keep them in RAM/encrypted RunStore, not logs. Errors contain constant codes.
Search is explicitly bounded lexical retrieval, not semantic/live equivalence.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from urllib.parse import urlsplit

ALLOWLIST = frozenset(("dataset_profile", "dataset_query", "dataset_chart", "run_code",
    "google_search", "internet_search", "personal_search", "personal_list_folders",
    "project_chat_read", "project_chats_list", "search_memory", "save_to_memory", "personal_save"))
# Kept separate to make accidental omission from the dispatcher visible in tests.
ALLOWLIST = ALLOWLIST | {"read_webpage"}


class ReplayError(Exception):
    """Constant code only, never the invalid value, URL, ID or validator text."""


def json_copy(value):
    def ensure_json(node, depth=0):
        if depth > 40:
            raise ReplayError("non_json_value")
        if type(node) is dict:
            if not all(type(k) is str for k in node):
                raise ReplayError("non_json_value")
            for child in node.values():
                ensure_json(child, depth + 1)
        elif type(node) is list:
            for child in node:
                ensure_json(child, depth + 1)
        elif node is not None and type(node) not in (str, int, float, bool):
            raise ReplayError("non_json_value")
    try:
        ensure_json(value)
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        return json.loads(encoded)
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise ReplayError("non_json_value") from None


def strict_loads(value):
    if isinstance(value, str):
        if len(value) > 1024 * 1024:
            raise ReplayError("arguments_too_large")
        def pairs(items):
            result = {}
            for key, val in items:
                if key in result:
                    raise ReplayError("duplicate_json_key")
                result[key] = val
            return result
        def reject_constant(_):
            raise ReplayError("non_json_value")
        try:
            value = json.loads(value, object_pairs_hook=pairs, parse_constant=reject_constant)
        except (ValueError, TypeError, RecursionError):
            raise ReplayError("arguments_invalid_json") from None
    return json_copy(value)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False, separators=(",", ":")).encode()).hexdigest()


_SCHEMA_KEYS = frozenset(("$schema", "$id", "$defs", "definitions", "$ref", "type", "properties",
    "required", "additionalProperties", "items", "enum", "const", "anyOf", "oneOf", "allOf",
    "title", "description", "default", "examples", "minimum", "maximum", "exclusiveMinimum",
    "exclusiveMaximum", "minLength", "maxLength", "minItems", "maxItems", "uniqueItems"))
_TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}


def _resolve(schema, root):
    ref = schema.get("$ref")
    if ref is None:
        return schema
    if not isinstance(ref, str) or not ref.startswith(("#/$defs/", "#/definitions/")):
        raise ReplayError("schema_reference_unsupported")
    node = root
    try:
        for part in ref[2:].split("/"):
            node = node[part.replace("~1", "/").replace("~0", "~")]
    except (KeyError, TypeError):
        raise ReplayError("schema_reference_missing") from None
    if not isinstance(node, dict):
        raise ReplayError("schema_invalid")
    return node


def check_schema(schema, root=None, depth=0):
    """Fail closed on schema dialect/features not actually implemented."""
    if root is None:
        root = schema
    if depth > 30 or not isinstance(schema, dict) or set(schema) - _SCHEMA_KEYS:
        raise ReplayError("schema_unsupported")
    if "$schema" in schema and schema["$schema"] not in (
            "https://json-schema.org/draft/2020-12/schema", "http://json-schema.org/draft-07/schema#"):
        raise ReplayError("schema_dialect_unsupported")
    if "$ref" in schema:
        check_schema(_resolve(schema, root), root, depth + 1)
    typ = schema.get("type")
    if typ is not None and (not isinstance(typ, str) or typ not in _TYPES):
        raise ReplayError("schema_unsupported")
    for key in ("properties", "$defs", "definitions"):
        if key in schema:
            if not isinstance(schema[key], dict):
                raise ReplayError("schema_invalid")
            for child in schema[key].values():
                check_schema(child, root, depth + 1)
    if "required" in schema and (not isinstance(schema["required"], list) or
            not all(isinstance(x, str) for x in schema["required"]) or
            len(set(schema["required"])) != len(schema["required"])):
        raise ReplayError("schema_invalid")
    for key in ("anyOf", "oneOf", "allOf"):
        if key in schema:
            if not isinstance(schema[key], list) or not schema[key]:
                raise ReplayError("schema_invalid")
            for child in schema[key]:
                check_schema(child, root, depth + 1)
    if "items" in schema:
        check_schema(schema["items"], root, depth + 1)
    if "additionalProperties" in schema and type(schema["additionalProperties"]) is not bool:
        check_schema(schema["additionalProperties"], root, depth + 1)
    for key in ("minLength", "maxLength", "minItems", "maxItems"):
        if key in schema and (type(schema[key]) is not int or schema[key] < 0):
            raise ReplayError("schema_invalid")
    for key in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"):
        if key in schema and (type(schema[key]) not in (float, int) or not math.isfinite(schema[key])):
            raise ReplayError("schema_invalid")
    if "enum" in schema and (not isinstance(schema["enum"], list) or not schema["enum"]):
        raise ReplayError("schema_invalid")
    if "uniqueItems" in schema and type(schema["uniqueItems"]) is not bool:
        raise ReplayError("schema_invalid")


def validate(value, schema, root=None, depth=0, tool_root=False):
    if root is None:
        root = schema
    if depth > 30:
        raise ReplayError("arguments_nesting_limit")
    if "$ref" in schema:
        validate(value, _resolve(schema, root), root, depth + 1, tool_root)
    for keyword in ("anyOf", "oneOf", "allOf"):
        if keyword not in schema:
            continue
        accepted = 0
        for child in schema[keyword]:
            try:
                validate(value, child, root, depth + 1, tool_root)
                accepted += 1
            except ReplayError:
                pass
        if ((keyword == "anyOf" and not accepted) or (keyword == "oneOf" and accepted != 1)
                or (keyword == "allOf" and accepted != len(schema[keyword]))):
            raise ReplayError("arguments_schema_mismatch")
    typ = schema.get("type")
    matches = {"object": type(value) is dict, "array": type(value) is list,
               "string": type(value) is str, "integer": type(value) is int,
               "number": type(value) in (int, float), "boolean": type(value) is bool,
               "null": value is None}
    if typ is not None and not matches[typ]:
        raise ReplayError("arguments_type_mismatch")
    if "enum" in schema and not any(type(value) is type(v) and value == v for v in schema["enum"]):
        raise ReplayError("arguments_enum_mismatch")
    if "const" in schema and (type(value) is not type(schema["const"]) or value != schema["const"]):
        raise ReplayError("arguments_const_mismatch")
    if type(value) is dict:
        props = schema.get("properties", {})
        if not all(isinstance(k, str) for k in value):
            raise ReplayError("arguments_type_mismatch")
        if any(k not in value for k in schema.get("required", [])):
            raise ReplayError("arguments_required_missing")
        # Pydantic often omits additionalProperties. Tool kwargs are deliberately
        # stricter: user_id/arm/settings cannot be smuggled into an execution ctx.
        extra = schema.get("additionalProperties", not tool_root)
        for key, child in value.items():
            if key in props:
                validate(child, props[key], root, depth + 1)
            elif extra is False or tool_root:
                raise ReplayError("arguments_unknown_property")
            elif isinstance(extra, dict):
                validate(child, extra, root, depth + 1)
    if type(value) in (int, float):
        if not math.isfinite(value):
            raise ReplayError("non_json_value")
        for key, valid in (("minimum", lambda x: value >= x), ("maximum", lambda x: value <= x),
                           ("exclusiveMinimum", lambda x: value > x), ("exclusiveMaximum", lambda x: value < x)):
            if key in schema and not valid(schema[key]):
                raise ReplayError("arguments_bounds_mismatch")
    if type(value) is str:
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", 1024 * 1024):
            raise ReplayError("arguments_bounds_mismatch")
    if type(value) is list:
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", 10000):
            raise ReplayError("arguments_bounds_mismatch")
        if schema.get("uniqueItems") and len({fingerprint(v) for v in value}) != len(value):
            raise ReplayError("arguments_unique_items_mismatch")
        for child in value:
            validate(child, schema.get("items", {}), root, depth + 1)


def tokens(text):
    return set(re.findall(r"[^\W_]+", text.casefold(), flags=re.UNICODE))


def ranked(query, documents, limit):
    wanted = tokens(query)
    if not wanted:
        raise ReplayError("query_empty")
    scores = []
    for doc in documents:
        text = (doc.get("title") or doc.get("key") or "") + " " + doc.get("text", doc.get("value", ""))
        overlap = len(wanted & tokens(text))
        if overlap:
            scores.append((-overlap, fingerprint(doc), doc))
    return [doc for _, _, doc in sorted(scores, key=lambda item: (item[0], item[1]))[:limit]]


def valid_url(url):
    try:
        p = urlsplit(url)
        return p.scheme in ("http", "https") and bool(p.netloc) and not p.username and not p.password
    except ValueError:
        return False


def failure(code):
    action = {
        "executor_unavailable": "Provision a new owned network-isolated executor; never use a running source stack or a recorded result.",
        "dataset_unavailable": "Acquire the explicitly selected original raw dataset/sheet in encrypted storage and an isolated local implementation.",
        "resource_missing": "Resolve the exact encrypted source resource reference; there is no live-network or historical-answer fallback.",
        "resource_incomplete": "Acquire the full original body/transcript/catalog, not an excerpt or profile pretending to be raw data.",
        "resource_conflict": "Choose a source-backed frozen snapshot explicitly; conflicting captures cannot be selected by call order.",
        "time_filter_unsupported": "Captured documents lack sufficient publication-time evidence for this time filter.",
        "raw_content_unavailable": "Search snippets are not full raw webpage content.",
    }.get(code, "Correct the declared contract, arguments, or explicitly selected resource; no external call was made.")
    return {"ok": False, "error": {"code": code, "action": action}, "remote_mutations": 0}


class ReplayTools:
    """One instance PER case PER arm. All inputs and outputs are deep-copied."""
    def __init__(self, contracts, resources, arm):
        if not isinstance(arm, str) or not arm:
            raise ReplayError("arm_invalid")
        self.arm = arm
        self._contracts = json_copy(contracts)
        self._resources = json_copy(resources)
        self._events = []
        if not isinstance(self._contracts, dict) or not isinstance(self._resources, dict):
            raise ReplayError("resource_invalid")
        for name, contract in self._contracts.items():
            if name not in ALLOWLIST or not isinstance(contract, dict) or contract.get("name") != name:
                raise ReplayError("tool_not_allowed")
            if not isinstance(contract.get("schema_source"), str) or not contract["schema_source"]:
                raise ReplayError("schema_provenance_missing")
            schema = contract.get("parameters")
            check_schema(schema)
            if schema.get("type") != "object":
                raise ReplayError("schema_tool_root_not_object")
            # Defaults are themselves validated, not an untyped backdoor.
            for prop in schema.get("properties", {}).values():
                if "default" in prop:
                    validate(prop["default"], prop, schema)
        self._validate_resources()

    def _validate_resources(self):
        specs = {"web_documents": ("url", "title", "text", "provenance"),
                 "pages": ("url", "title", "body", "complete", "provenance"),
                 "threads": ("thread_id", "title", "messages", "complete", "authorized", "provenance"),
                 "memories": ("key", "value", "scope", "provenance"),
                 "folders": (), "datasets": ()}
        for key, required in specs.items():
            rows = self._resources.get(key, [])
            if not isinstance(rows, list):
                raise ReplayError("resource_invalid")
            for row in rows:
                if key == "folders":
                    if not isinstance(row, str):
                        raise ReplayError("resource_invalid")
                    continue
                if not isinstance(row, dict) or any(k not in row for k in required):
                    raise ReplayError("resource_invalid")
                if required and (not isinstance(row.get("provenance"), dict) or not row["provenance"]):
                    raise ReplayError("resource_provenance_missing")
                if key in ("pages", "web_documents"):
                    if not isinstance(row["url"], str) or not valid_url(row["url"]):
                        raise ReplayError("resource_invalid")
                    if "final_url" in row and (not isinstance(row["final_url"], str) or not valid_url(row["final_url"])):
                        raise ReplayError("resource_invalid")
                    for field in ("title", "body" if key == "pages" else "text"):
                        if not isinstance(row[field], str):
                            raise ReplayError("resource_invalid")
                if key == "pages" and (type(row["complete"]) is not bool or
                        type(row.get("total_chars")) is not int or row["total_chars"] < len(row["body"]) or
                        (row["complete"] and row["total_chars"] != len(row["body"]))):
                    raise ReplayError("resource_invalid")
                if key == "threads":
                    if (not isinstance(row["thread_id"], str) or not isinstance(row["title"], str) or
                            type(row["complete"]) is not bool or type(row["authorized"]) is not bool or
                            not isinstance(row["messages"], list)):
                        raise ReplayError("resource_invalid")
                    for message in row["messages"]:
                        if (not isinstance(message, dict) or message.get("role") not in ("user", "assistant", "system", "tool")
                                or not isinstance(message.get("content"), str)):
                            raise ReplayError("resource_invalid")
                if key == "memories":
                    if row["scope"] not in ("personal", "memory") or not all(isinstance(row[k], str) for k in ("key", "value")):
                        raise ReplayError("resource_invalid")
        if not isinstance(self._resources.get("coverage", {}), dict):
            raise ReplayError("resource_invalid")

    def clone(self, arm):
        """Clone current state deliberately; new independent arms use same seed."""
        return ReplayTools(self._contracts, self._resources, arm)

    def state(self):
        return json_copy(self._resources)

    def events(self):
        return json_copy(self._events)

    def dispatch(self, name, arguments):
        """Public errors are constant; successes are sensitive, RAM-only values."""
        try:
            if not isinstance(name, str) or name not in ALLOWLIST:
                raise ReplayError("tool_not_allowed")
            if name not in self._contracts:
                raise ReplayError("schema_missing")
            args = strict_loads(arguments)
            if not isinstance(args, dict):
                raise ReplayError("arguments_type_mismatch")
            schema = self._contracts[name]["parameters"]
            validate(args, schema, tool_root=True)
            args = copy.deepcopy(args)
            for key, prop in schema.get("properties", {}).items():
                if key not in args and "default" in prop:
                    args[key] = copy.deepcopy(prop["default"])
            validate(args, schema, tool_root=True)
            result = self._execute(name, args)
            result = {"ok": True, "result": json_copy(result), "resource_scope": "frozen_local_snapshot",
                      "remote_mutations": 0}
        except ReplayError as error:
            result = failure(error.args[0])
        except Exception:
            # No repr/str(error): library errors can contain the entire document.
            result = failure("adapter_internal_error")
        self._events.append({"sequence": len(self._events), "name": name if isinstance(name, str) and name in ALLOWLIST else "not_allowed",
                             "ok": result["ok"], "error_code": result.get("error", {}).get("code")})
        return result

    def _need_coverage(self, scope):
        if self._resources.get("coverage", {}).get(scope) not in ("complete", "captured_documents_only"):
            raise ReplayError("resource_missing")

    def _execute(self, name, args):
        if name == "run_code":
            raise ReplayError("executor_unavailable")
        if name in ("dataset_profile", "dataset_query", "dataset_chart"):
            # Even a recorded profile is NOT the underlying data. There is no
            # executor hook until a separately owned isolated implementation exists.
            raise ReplayError("dataset_unavailable")
        if name == "read_webpage":
            url = args["url"]
            if not valid_url(url):
                raise ReplayError("url_invalid")
            pages = [p for p in self._resources.get("pages", []) if p["url"] == url]
            if not pages:
                raise ReplayError("resource_missing")
            complete = [p for p in pages if p["complete"]]
            if not complete:
                raise ReplayError("resource_incomplete")
            if len({fingerprint([p["body"], p["title"], p.get("final_url", p["url"])]) for p in complete}) != 1:
                raise ReplayError("resource_conflict")
            page = complete[0]
            limit = min(20000, max(500, args.get("max_chars", 8000) or 8000))
            body = page["body"][:limit]
            return {"success": True, "url": page.get("final_url", url), "title": page["title"], "content": body,
                    "truncated": len(body) < len(page["body"]), "total_chars": len(page["body"])}
        if name in ("google_search", "internet_search"):
            self._need_coverage("web")
            docs = self._resources.get("web_documents", [])
            if not docs:
                raise ReplayError("resource_missing")
            if args.get("time_range"):
                raise ReplayError("time_filter_unsupported")
            if args.get("include_raw_content"):
                raise ReplayError("raw_content_unavailable")
            topic = args.get("topic", "general")
            if topic != "general":
                docs = [d for d in docs if d.get("topic") == topic]
                if not docs:
                    raise ReplayError("resource_missing")
            limit = max(1, min(10, args.get("num", args.get("max_results", 5))))
            selected = ranked(args["query"], docs, limit * 10)
            # One URL may have several captured snippets. Return best text per URL,
            # not duplicate the apparent evidence count by repeated source queries.
            results, seen = [], set()
            for doc in selected:
                if doc["url"] in seen:
                    continue
                seen.add(doc["url"])
                results.append({"title": doc["title"], "link": doc["url"], "snippet": doc["text"][:2000]})
                if len(results) == limit:
                    break
            return {"success": True, "query": args["query"], "results": results,
                    "retrieval": "bounded_local_lexical_index", "snapshot_complete": False}
        if name == "project_chats_list":
            self._need_coverage("threads")
            threads = [t for t in self._resources.get("threads", []) if t["authorized"]]
            threads = sorted(threads, key=lambda t: (t.get("order", 0), t["thread_id"]))
            offset = max(0, args.get("offset", 0))
            page = threads[offset:offset + 50]
            if offset >= len(threads) and self._resources["coverage"]["threads"] != "complete":
                raise ReplayError("resource_incomplete")
            return {"chats": [{k: t[k] for k in ("thread_id", "title")} for t in page],
                    "snapshot_complete": self._resources["coverage"]["threads"] == "complete",
                    "next_offset": offset + 50 if len(threads) > offset + 50 else None}
        if name == "project_chat_read":
            threads = [t for t in self._resources.get("threads", []) if t["thread_id"] == args["thread_id"] and t["authorized"]]
            if not threads:
                raise ReplayError("resource_missing")
            if len(threads) != 1:
                raise ReplayError("resource_conflict")
            thread = threads[0]
            if not thread["complete"]:
                raise ReplayError("resource_incomplete")
            query = args.get("query", "")
            messages = thread["messages"]
            if query.strip():
                # repository/message_repository.py:174 uses escaped literal
                # substrings with flexible whitespace, NOT token-OR retrieval.
                pattern = re.compile(r"\s+".join(re.escape(word) for word in query.split()), re.IGNORECASE)
                messages = [m for m in messages if pattern.search(m["content"])]
                messages = messages[:50]
            else:
                messages = messages[-max(1, min(50, args.get("last_n", 20) or 20)):]
            return {"thread_id": thread["thread_id"], "title": thread["title"], "messages": messages,
                    "total_messages": len(thread["messages"])}
        if name in ("personal_search", "search_memory"):
            scope = "personal" if name == "personal_search" else "memory"
            self._need_coverage(scope)
            docs = [m for m in self._resources.get("memories", []) if m["scope"] == scope]
            folder = args.get("folder", "").strip().lower().replace(" ", "_")[:32]
            if folder:
                docs = [m for m in docs if m.get("folder", "") == folder]
            hits = ranked(args["query"], docs, max(1, min(10, args.get("top_k", 10))))
            return {"results": [{"key": m["key"], "value": m["value"], "folder": m.get("folder", "")} for m in hits],
                    "retrieval": "bounded_local_lexical_index", "snapshot_complete": self._resources["coverage"][scope] == "complete"}
        if name == "personal_list_folders":
            self._need_coverage("folders")
            return {"folders": sorted(set(self._resources.get("folders", [])))}
        if name in ("personal_save", "save_to_memory"):
            scope = "personal" if name == "personal_save" else "memory"
            self._need_coverage(scope)
            key = args.get("title", "") if name == "personal_save" else args["key"]
            value = args["text"] if name == "personal_save" else args["value"]
            folder = args.get("folder", "").strip().lower().replace(" ", "_")[:32]
            row = {"key": key, "value": value, "folder": folder, "scope": scope,
                   "provenance": {"kind": "owned_arm_local_write", "sequence": len(self._events)}}
            rows = self._resources.setdefault("memories", [])
            rows[:] = [m for m in rows if (m["scope"], m["key"], m.get("folder", "")) != (scope, key, folder)]
            rows.append(row)
            if folder:
                self._resources.setdefault("folders", []).append(folder)
            return {"saved": True, "local_only": True}
        raise ReplayError("adapter_unsupported")
