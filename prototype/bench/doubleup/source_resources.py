"""Data-only replay preparation. Credentials and source bodies never reach stdout.

The optional Mongo step performs bounded projected reads, not registry imports:
repository constructors create indexes and tool builders activate integrations.
All resource locators/content and declared schemas belong in an encrypted RunStore.
No S3 download, model request, sandbox execution, or source mutation is provided.
"""
from __future__ import annotations

import argparse
import ast
import collections
import json
from pathlib import Path
import re
import subprocess
import sys

from .storage import PilotError, RunStore, canonical, digest, hashed

SOURCE_RUN = "mongo-dialogues-application-normalized-v2"
BACKEND = Path("/Users/igor/Projects/Obscura/.claude/worktrees/doubleup-backend-pilot")
NAMES = frozenset(("dataset_profile", "google_search", "internet_search", "personal_list_folders",
                   "personal_search", "project_chat_read", "project_chats_list", "read_webpage",
                   "run_code", "search_memory"))
SIGNATURES = {
    "google_search": ("tools/search_tools.py", "google_search"),
    "internet_search": ("tools/web_search_tool.py", "internet_search"),
    "read_webpage": ("tools/read_webpage_tool.py", "read_webpage"),
    "project_chat_read": ("tools/project_chat_tools.py", "project_chat_read"),
    "project_chats_list": ("tools/project_chat_tools.py", "project_chats_list"),
    "personal_search": ("tools/personal_storage_tools.py", "personal_search"),
    "personal_list_folders": ("tools/personal_storage_tools.py", "personal_list_folders"),
    "search_memory": ("tools/memory_tools.py", "search_memory"),
    "dataset_profile": ("tools/dataset_tools.py", "dataset_profile"),
    "run_code": ("tools/run_code_tool.py", "run_code"),
}

# Only these fields cross the reader boundary. No settings/env/config/provider
# objects are fetched, even encrypted: those may contain infrastructure secrets.
MONGO_READER = r'''
import json,sys,logging
from pymongo import MongoClient
from bson import json_util
logging.disable(logging.CRITICAL)
cfg=json.loads(sys.stdin.buffer.read())
try:
 with MongoClient(cfg['uri'],serverSelectionTimeoutMS=5000,connectTimeoutMS=5000,
                  socketTimeoutMS=20000,appname='doubleup-local-readonly-replay-contracts') as client:
  db=client[cfg['database']]
  names=cfg['names']
  tools=list(db.tools_registry.find({'name':{'$in':names}},
             {'_id':0,'name':1,'schema':1,'description':1,'module':1,'enabled':1}).limit(40).max_time_ms(10000))
  graphs=[]; bindings=[]; prompts=[]
  for ident in cfg['identities']:
   gid=ident['graph_id']
   graph=db.graphs.find_one({'graph_id':gid},{'_id':0,'graph_id':1,'name':1,'type':1,
         'builtin_id':1,'system_prompt':1,'prompt':1,'description':1,'enabled':1})
   if graph:graphs.append(graph)
   # Settings deliberately excluded: several integrations keep credentials there.
   q={'graph_id':gid,'user_id':ident['user_id']}
   if ident.get('org_id'):q['org_id']=ident['org_id']
   bindings.extend(list(db.user_tool_graphs.find(q,{'_id':0,'graph_id':1,'tool_id':1,'enabled':1}).limit(100).max_time_ms(10000)))
   pq={'graph_id':gid,'$or':[{'user_id':ident['user_id']},{'user_id':None,'org_id':ident.get('org_id')},{'user_id':None,'org_id':None}]}
   prompts.extend(list(db.prompts.find(pq,{'_id':0,'graph_id':1,'key':1,'system_prompt':1,'user_prompt':1}).limit(20).max_time_ms(10000)))
  print(json_util.dumps({'ok':True,'tools':tools,'graphs':graphs,'bindings':bindings,'prompts':prompts},json_options=json_util.CANONICAL_JSON_OPTIONS))
except Exception:
 print('{"ok":false,"error_code":"replay_selected_mongo_read_failed"}')
'''


def parse_json(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, UnicodeDecodeError):
            return value
    return value


def unique_calls(case):
    """Refuse conflicting ID variants; execution spans never create extra calls."""
    result = {}
    for row in case.get("source_context", {}).get("tool_evidence", {}).get("calls", []):
        cid = row.get("call_id")
        if not cid:
            continue
        if cid in result and any(row.get(k) != result[cid].get(k) for k in ("name", "arguments")):
            raise PilotError("replay_ambiguous_source_call")
        result[cid] = row
    return list(result.values())


def source_signatures():
    """AST-only inventory of actual declared signatures. Never import source tools.

    This is declaration provenance, not a new inferred schema. Mongo's actual
    Pydantic schema is preferred; these signatures detect stale registry rows.
    """
    result = {}
    for name, (rel, function) in SIGNATURES.items():
        path = BACKEND / rel
        source = path.read_text()
        tree = ast.parse(source)
        functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == function]
        if len(functions) != 1:
            raise PilotError("replay_source_signature_ambiguous")
        f = functions[0]
        args = f.args.args
        defaults = [None] * (len(args) - len(f.args.defaults)) + list(f.args.defaults)
        constants = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                try:
                    constants[node.targets[0].id] = ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    pass
        fields = []
        for arg, default in zip(args, defaults):
            field = {"name": arg.arg, "annotation": ast.unparse(arg.annotation) if arg.annotation else None,
                     "required": default is None}
            if default is not None:
                try:
                    field["default"] = constants[default.id] if isinstance(default, ast.Name) else ast.literal_eval(default)
                except (KeyError, ValueError, TypeError):
                    raise PilotError("replay_source_default_unsupported") from None
            fields.append(field)
        result[name] = {"path": rel, "line": f.lineno, "sha256": digest(source.encode()),
                        "fields": fields, "docstring": ast.get_docstring(f) or ""}
    return result


def annotation_schema(annotation):
    if isinstance(annotation, ast.Name) and annotation.id in ("str", "int", "bool", "float"):
        return {"type": {"str": "string", "int": "integer", "bool": "boolean", "float": "number"}[annotation.id]}
    if isinstance(annotation, ast.Subscript) and isinstance(annotation.value, ast.Name):
        if annotation.value.id == "Optional":
            return {"anyOf": [annotation_schema(annotation.slice), {"type": "null"}]}
        if annotation.value.id == "Literal":
            try:
                vals = ast.literal_eval(annotation.slice)
            except (ValueError, TypeError):
                raise PilotError("replay_source_annotation_unsupported") from None
            vals = list(vals) if isinstance(vals, tuple) else [vals]
            if vals and all(type(v) is str for v in vals):
                return {"type": "string", "enum": vals}
    raise PilotError("replay_source_annotation_unsupported")


def declared_schema(signature):
    """Lossless supported signature subset; unknown annotations fail CLOSED.

    Used only for dynamic context tools absent from tools_registry. Names,
    argument spellings, types and defaults come from the source declaration,
    never from an observed call. Complex declarations require registry schemas.
    """
    props, required = {}, []
    for field in signature["fields"]:
        annotation = ast.parse(field["annotation"], mode="eval").body
        prop = annotation_schema(annotation)
        if field["required"]:
            required.append(field["name"])
        else:
            prop["default"] = field["default"]
        props[field["name"]] = prop
    return {"type": "object", "properties": props, "required": required}


def safe_projection(value):
    """Drop suspect secret-bearing strings rather than archive credentials."""
    if isinstance(value, str):
        if re.search(r"(?i)(mongodb(?:\+srv)?://|postgres(?:ql)?://|redis://|-----BEGIN .*PRIVATE KEY|(?:api[_-]?key|secret|password|authorization)\s*[:=]\s*\S+|\b(?:sk|pk)-[A-Za-z0-9_-]{16,})", value):
            return {"excluded": "credential_bearing_text"}
        return value
    if isinstance(value, list):
        return [safe_projection(v) for v in value]
    if isinstance(value, dict):
        return {k: safe_projection(v) for k, v in value.items()}
    return value


def normalize_ejson(value):
    if isinstance(value, dict):
        if len(value) == 1:
            for key in ("$numberInt", "$numberLong"):
                if key in value:
                    return int(value[key])
            if "$numberDouble" in value:
                return float(value["$numberDouble"])
        return {k: normalize_ejson(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize_ejson(v) for v in value]
    return value


def collect_contracts(cases, store, mongo=False, archived_docs_run=None):
    signatures = source_signatures()
    response = {"tools": [], "graphs": [], "bindings": [], "prompts": []}
    if archived_docs_run:
        archive = RunStore(archived_docs_run, False)
        archive.verify()
        response = archive.read_encrypted("selected-contract-docs.aesgcm")
    if mongo:
        from .mongo_intake import read_config, IMAGE
        identities = []
        for case in cases:
            ident = {k: case["thread"].get(k) for k in ("graph_id", "user_id", "org_id")}
            if ident not in identities:
                identities.append(ident)
        config = {**read_config(), "identities": identities, "names": sorted(NAMES)}
        try:
            process = subprocess.run(["docker", "run", "--rm", "--pull", "never", "--network", "host",
                "--log-driver", "none", "--read-only", "--cap-drop", "ALL", "--security-opt",
                "no-new-privileges", "--pids-limit", "64", "--memory", "256m", "-i", IMAGE,
                "python", "-c", MONGO_READER], input=canonical(config), capture_output=True, timeout=90)
        except (OSError, subprocess.SubprocessError):
            raise PilotError("replay_selected_mongo_reader_unavailable") from None
        if process.returncode or len(process.stdout) > 8 * 1024 * 1024:
            raise PilotError("replay_selected_mongo_reader_refused")
        try:
            response = json.loads(process.stdout)
        except (ValueError, UnicodeDecodeError):
            raise PilotError("replay_selected_mongo_reader_invalid") from None
        if response.get("ok") is not True:
            raise PilotError("replay_selected_mongo_read_failed")
    response = safe_projection(response)
    store.encrypt("selected-contract-docs.aesgcm", response)
    contracts = {}
    for name in sorted(NAMES):
        signature = signatures[name]
        expected = declared_schema(signature)
        rows = [row for row in response["tools"] if row.get("name") == name and isinstance(row.get("schema"), dict)]
        schemas = {hashed(row["schema"]): row for row in rows}
        if len(schemas) > 1:
            raise PilotError("replay_registry_schema_conflict")
        if schemas:
            row = next(iter(schemas.values()))
            schema = normalize_ejson(row["schema"])
            # Same names/types/defaults, or block: registry drift is not permission
            # to silently accept whichever contract fits observed arguments.
            keys = ("type", "enum", "default", "anyOf")
            actual = schema.get("properties", {})
            if set(actual) != set(expected["properties"]) or set(schema.get("required", [])) != set(expected["required"]):
                raise PilotError("replay_registry_source_signature_drift")
            for key, prop in expected["properties"].items():
                if any(actual[key].get(k) != prop.get(k) for k in keys):
                    raise PilotError("replay_registry_source_signature_drift")
            origin = "mongo.tools_registry.schema"
            description = row.get("description")
            if not isinstance(description, str) or not description:
                description = signature["docstring"]
        else:
            schema = expected
            origin = "backend.declared_function_signature_ast"
            description = signature["docstring"]
        contracts[name] = {"name": name, "parameters": schema, "description": description,
                           "schema_source": origin, "declaration": signature,
                           "historical_declaration": False}
    store.encrypt("tool-contracts.aesgcm", contracts)
    return contracts


def source_ref(case_index, pointer):
    return {"run": SOURCE_RUN, "artifact": "full-dialogues.aesgcm",
            "pointer": "/dialogues/" + str(case_index) + pointer}


def captured_memory_documents(output, scope, ref):
    """Parse only the source renderer's document boundaries, never whole replies."""
    if not isinstance(output, str):
        return []
    if scope == "personal":
        marker = "**Заметки из памяти:**\n"
        if marker not in output:
            return []
        text = output.split(marker, 1)[1]
        text = re.split(r"\n(?:\*\*Фрагменты|\*\*\d+\.)", text, maxsplit=1)[0]
    else:
        if not output.startswith(("Найдено в памяти:\n", "Найдено в личной памяти:\n")):
            return []
        text = output.split("\n", 1)[1]
    matches = list(re.finditer(r"(?m)^- ([^\n:]+): ", text))
    docs = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        value = text[match.end():end].rstrip("\n")
        if value:
            docs.append({"key": match.group(1), "value": value, "scope": scope,
                         "provenance": dict(ref, rendered_document_index=i)})
    return docs


def captured_catalog(output, args, ref):
    if not isinstance(output, str) or not isinstance(args, dict):
        return [], False
    header = re.match(r"^Чаты проекта, доступные пользователю \((\d+), offset=(\d+)\):", output)
    if not header:
        return [], False
    matches = list(re.finditer(r"(?m)^- thread_id=([^\n|]+) \| «(.*?)»", output))
    rows = [{"thread_id": m.group(1).strip(), "title": m.group(2), "messages": [],
             "authorized": True, "complete": False, "order": int(header.group(2)) + i,
             "provenance": dict(ref, catalog_row=i)} for i, m in enumerate(matches)]
    complete = (int(header.group(2)) == 0 and args.get("offset", 0) == 0
                and len(rows) == int(header.group(1)) and "Есть следующая страница:" not in output)
    return rows, complete


def captured_transcript(output, args, ref, current_thread_id):
    if not isinstance(output, str) or not isinstance(args, dict) or not isinstance(args.get("thread_id"), str):
        return None
    header = re.match(r"^Чат «(.*?)» \(автор: .*?\), последние (\d+) сообщений из (\d+):\n", output)
    if not header:
        return None
    body = output[header.end():]
    # This is the actual source delimiter. Unknown/legacy renderers remain
    # unresolved instead of guessing message boundaries in customer prose.
    if "\nСсылка на чат: " not in body:
        return None
    body = body.rsplit("\nСсылка на чат: ", 1)[0]
    matches = list(re.finditer(r"(?m)^\[(пользователь|ассистент) · [^\]\n]*\] ", body))
    messages = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        messages.append({"role": "user" if match.group(1) == "пользователь" else "assistant",
                         "content": body[match.end():end].rstrip("\n")})
    shown, total = int(header.group(2)), int(header.group(3))
    return {"thread_id": args["thread_id"], "title": header.group(1), "messages": messages,
            "complete": shown == total == len(messages) and args["thread_id"] != current_thread_id,
            "authorized": True, "provenance": ref}


def attachment_locators(case, case_index):
    """Exact encrypted pointers identify selected bytes needed BEFORE any S3 read."""
    result = []
    fields = {"doc_id", "file_id", "filename", "file_name", "s3_key", "parquet_key", "dataset_id",
              "content_type", "size", "size_bytes", "selected_sheet", "sheets", "url", "download_url"}
    def visit(node, pointer):
        if isinstance(node, dict):
            # A URL in arbitrary prose is not an approved attachment. Require
            # explicit file/dataset identity or a real attachment envelope.
            if any(k in node for k in ("doc_id", "file_id", "filename", "file_name", "s3_key", "parquet_key", "dataset_id")):
                role = ("original_user_attachment" if pointer.startswith(("/user_turns/", "/mongo_user_messages/")) else
                        "historical_generated_output_do_not_seed" if "generated" in pointer.lower() else
                        "unresolved_checkpoint_reference_not_approved_input")
                result.append({"locator": safe_projection({k: node[k] for k in fields if k in node}),
                    "ref": source_ref(case_index, pointer), "role": role,
                    "bytes_exported": False, "action": "Acquire only selected ORIGINAL USER INPUT bytes with approved existing read access. Historical generated artifacts must be regenerated by the new causal run, never seeded; do not list buckets."})
            for key, child in node.items():
                visit(child, pointer + "/" + key.replace("~", "~0").replace("/", "~1"))
        elif isinstance(node, list):
            for i, child in enumerate(node):
                visit(child, pointer + "/" + str(i))
    for key in ("user_turns", "mongo_user_messages", "checkpoint_proof"):
        visit(case.get(key), "/" + key)
    return result


def build_resources(case, case_index):
    """Extract immutable DOCUMENTS from tool execution outputs, never canned calls.

    Search snippets remain snippets. Only successful untruncated page bodies can
    satisfy a future read_webpage. Rendered project excerpts do not become full
    transcripts; an explicit resource acquisition task is emitted instead.
    """
    resources = {"web_documents": [], "pages": [], "threads": [], "memories": [],
                 "folders": [], "datasets": [], "missing": [], "attachment_requirements": attachment_locators(case, case_index),
                 "coverage": {"web": "captured_documents_only", "threads": "missing",
                              "personal": "missing", "memory": "missing", "folders": "missing"}}
    spans = case.get("source_context", {}).get("application_activity", {}).get("source_tool_execution_spans", [])
    catalog_seeded = False
    for index, span in enumerate(spans):
        name, args, output = span.get("name"), parse_json(span.get("arguments")), parse_json(span.get("result"))
        ref = source_ref(case_index, "/source_context/application_activity/source_tool_execution_spans/" + str(index))
        if name in ("internet_search", "google_search") and isinstance(output, dict):
            for ri, doc in enumerate(output.get("results", [])):
                if not isinstance(doc, dict):
                    continue
                url = doc.get("link", doc.get("url"))
                text = doc.get("snippet", doc.get("content"))
                if isinstance(url, str) and isinstance(text, str) and text:
                    resources["web_documents"].append({"url": url, "title": doc.get("title") or "",
                        "text": text, "kind": "captured_search_snippet", "provenance": dict(ref, result_index=ri),
                        "topic": args.get("topic", "general") if isinstance(args, dict) else "general"})
        elif name == "read_webpage" and isinstance(output, dict) and isinstance(args, dict):
            url, body = args.get("url"), output.get("content")
            if output.get("success") is True and isinstance(url, str) and isinstance(body, str) and isinstance(output.get("url"), str):
                complete = output.get("truncated") is False and output.get("total_chars") == len(body)
                page = {"url": url, "final_url": output["url"], "title": output.get("title") or "", "body": body,
                        "complete": complete, "total_chars": output.get("total_chars"), "provenance": ref}
                resources["pages"].append(page)
                if page["final_url"] != url:
                    # Only an actually observed redirect gets this exact alias;
                    # no URL normalization or query-string wildcard is allowed.
                    resources["pages"].append(dict(page, url=page["final_url"]))
                resources["web_documents"].append({"url": page["final_url"], "title": page["title"], "text": body,
                    "kind": "captured_page_body" if complete else "captured_page_excerpt", "provenance": ref,
                    "topic": "general"})
                if not complete:
                    resources["missing"].append({"kind": "full_webpage_body", "locator": url, "ref": ref,
                        "action": "Acquire exact original full body; captured excerpt cannot serve arbitrary max_chars."})
            else:
                resources["missing"].append({"kind": "webpage_body", "locator": url, "ref": ref,
                    "action": "Original read failed or lacked an exact URL/body; no live network fallback."})
        elif name in ("project_chat_read", "project_chats_list", "personal_search", "personal_list_folders", "search_memory", "dataset_profile", "run_code"):
            resolved = False
            if name in ("personal_search", "search_memory"):
                scope = "personal" if name == "personal_search" else "memory"
                docs = captured_memory_documents(output, scope, ref)
                resources["memories"].extend(docs)
                if docs:
                    resources["coverage"][scope] = "captured_documents_only"
                    resolved = True
            elif name == "personal_list_folders" and output == "Личное хранилище пусто или папки ещё не созданы.":
                resources["coverage"]["folders"] = "complete"
                resolved = True
            elif name == "project_chats_list":
                rows, complete = captured_catalog(output, args, ref)
                if rows:
                    # Freeze FIRST captured catalog as seed; later calls are not
                    # an instruction to roll local state through historical time.
                    if not catalog_seeded:
                        existing = {r["thread_id"]: r for r in resources["threads"]}
                        selected = []
                        for row in rows:
                            prior = existing.pop(row["thread_id"], None)
                            if prior and prior["messages"]:
                                prior["order"] = row["order"]
                                selected.append(prior)
                            else:
                                selected.append(row)
                        resources["threads"] = selected + list(existing.values())
                        resources["coverage"]["threads"] = "complete" if complete else "captured_documents_only"
                        catalog_seeded = True
                    resolved = True
            elif name == "project_chat_read":
                row = captured_transcript(output, args, ref, case.get("thread", {}).get("thread_id"))
                if row:
                    old = [r for r in resources["threads"] if r["thread_id"] == row["thread_id"]]
                    if not old:
                        resources["threads"].append(row)
                    elif row["complete"] and not old[0]["complete"]:
                        row["order"] = old[0].get("order", 0)
                        resources["threads"] = [r for r in resources["threads"] if r["thread_id"] != row["thread_id"]] + [row]
                    resolved = row["complete"]
            if resolved:
                continue
            # Locators are sensitive; only this encrypted plan can contain them.
            resources["missing"].append({"kind": {"project_chat_read": "authorized_thread_transcript",
                "project_chats_list": "authorized_project_thread_catalog", "personal_search": "original_personal_documents",
                "personal_list_folders": "original_personal_folder_catalog", "search_memory": "original_memory_documents",
                "dataset_profile": "raw_dataset_snapshot", "run_code": "isolated_executor_and_selected_input_files"}[name],
                "locator": {k: args[k] for k in ("thread_id", "dataset_id", "sheet") if isinstance(args, dict) and k in args},
                "ref": ref, "action": "Resolve only explicitly selected original resources; do not convert historical tool text into success."})
    # Content-sensitive dedup retains variants; conflicting snapshots are refused
    # at dispatch rather than picking a favourable historical response.
    for key in ("web_documents", "pages"):
        unique = {}
        for doc in resources[key]:
            identity = hashed({k: v for k, v in doc.items() if k != "provenance"})
            unique.setdefault(identity, doc)
        resources[key] = list(unique.values())
    return resources


def make_plan(run_id, mongo=False, archived_docs_run=None):
    source = RunStore(SOURCE_RUN, False)
    source.verify()
    payload = source.read_encrypted("full-dialogues.aesgcm")
    cases = payload["dialogues"]
    store = RunStore(run_id, True)
    contracts = collect_contracts([cases[i] for i in (0, 3, 5)], store, mongo, archived_docs_run)
    from .replay_tools import ReplayTools
    plans, summaries = [], []
    for index, case in enumerate(cases):
        resources = build_resources(case, index)
        store.encrypt("resources-case-" + str(index) + ".aesgcm", resources)
        calls = unique_calls(case)
        adapters = ReplayTools(contracts, resources, arm="plan")
        supported, blocked = collections.Counter(), collections.Counter()
        requirements = []
        for call in calls:
            outcome = adapters.dispatch(call["name"], call["arguments"])
            if outcome["ok"]:
                supported[call["name"]] += 1
            else:
                blocked[call["name"]] += 1
                requirements.append({"call_id": call["call_id"], "name": call["name"],
                                     "error_code": outcome["error"]["code"], "source_provenance": call.get("provenance")})
        complete = bool(case.get("langfuse", {}).get("complete"))
        summary = {"case_index": index, "users": case["counts"]["user"], "langfuse_complete": complete,
                   "unique_id_linked_calls": len(calls), "tool_counts": dict(collections.Counter(c["name"] for c in calls)),
                   "source_execution_spans": len(case["source_context"]["application_activity"]["source_tool_execution_spans"]),
                   "supported_observed_calls": dict(supported), "blocked_observed_calls": dict(blocked),
                   "blocked_error_counts": dict(collections.Counter(r["error_code"] for r in requirements)),
                   "missing_resource_kind_counts": dict(collections.Counter(r["kind"] for r in resources["missing"])),
                   "attachment_role_counts": dict(collections.Counter(r["role"] for r in resources["attachment_requirements"])),
                   "source_join_pending": not complete,
                   "indexed_web_documents": len(resources["web_documents"]), "mirrored_pages": len(resources["pages"]),
                   "missing_resource_requirements": len(resources["missing"]),
                   "attachment_locator_records": len(resources["attachment_requirements"]),
                   "captured_memory_documents": len(resources["memories"]),
                   "authorized_catalog_threads": len(resources["threads"]),
                   "full_authorized_thread_transcripts": sum(t["complete"] for t in resources["threads"]),
                   "full_causal_replay_ready": False}
        summaries.append(summary)
        plans.append({**summary, "source": source_ref(index, ""), "blocked_calls": requirements,
                      "resource_artifact": "resources-case-" + str(index) + ".aesgcm"})
    store.encrypt("replay-plan.aesgcm", {"cases": plans, "integration": {
        "user_sequence": "Use source user_turns only, original order and multiplicity; no historical assistant/tool seeding.",
        "generation": "Lead-owned new model output through none/builtin/pseudex; then dispatch validated new calls; feed actual local returns to the next generation.",
        "arm_state": "Construct fresh ReplayTools per case and arm. Never share a mutable adapter or transplant historical results.",
        "missing_inputs": "Resolve encrypted per-case missing refs first. S3 reads require separately approved existing selected-resource read access. No broad listing.",
        "sandbox": "Existing owned contract: services/sandbox_client.py SandboxClient.execute_code(code, table_parquet, timeout_sec, files). Provision a NEW owned network-none isolated executor, resource-limited read-only container, private per-arm work storage; do not reuse running stacks. Not implemented/activated here.",
        "comparability": "Current registry/source declarations are current, not proven historical. Captured search is a bounded lexical index, not live semantic/provider equivalence.",
        "errors": "Unsupported is not success and not comparable execution. Preserve code/actionability; no historical-answer fallback."}})
    manifest = store.finish({"kind": "safe-local-replay-plan", "cases": summaries,
        "schema_sources": dict(collections.Counter(c["schema_source"] for c in contracts.values())),
        "tool_names": sorted(contracts), "provider_calls": 0, "remote_mutations": 0, "source_code_executed": False,
        "credentials_archived": False, "docker_logging": "none" if mongo else "not_used", "causal_replay_executed": False})
    return {"run_id": run_id, "cases": summaries, "schema_sources": manifest["schema_sources"],
            "provider_calls": 0, "remote_mutations": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--read-selected-mongo-contracts", action="store_true")
    parser.add_argument("--archived-contract-docs-run")
    args = parser.parse_args()
    try:
        print(json.dumps(make_plan(args.run_id, args.read_selected_mongo_contracts, args.archived_contract_docs_run), ensure_ascii=False))
    except Exception:
        # Never stringify an exception: drivers/validators may embed URIs or data.
        print('{"ok":false,"error_code":"replay_plan_preparation_failed"}', file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
