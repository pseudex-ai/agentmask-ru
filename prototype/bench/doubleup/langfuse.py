"""Bounded GET-only Langfuse connector; credentials never enter logs/artifacts.

Adapted conceptually from 2up/ops/eval/prodimex-document-compare/export_langfuse.py:
Basic auth, host allowlist, nested LiteLLM attribution. No scrubber, fixed tenant,
fixed date or plaintext writer is reused. Redirects and environment proxies are
refused: the allowlist must govern the actual credential destination, not just
its first hop. No SDK/ingestion/provider clients are involved.
"""

import base64
import datetime as dt
import json
import os
import re
import socket
import ssl
import stat
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .storage import PilotError, digest, hashed

HOST = "https://langfuse.inf.2up.dev"
CREDENTIAL_FILE = Path.home() / ".config/2up/langfuse.env"
MAX_RESPONSE = 64 * 1024 * 1024


def credentials(path=CREDENTIAL_FILE):
    # Parse dotenv as data, never shell-source/eval a credential file.
    if path.is_symlink():
        raise PilotError("credential_symlink_refused")
    info = path.stat()
    if stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != os.getuid():
        raise PilotError("credential_file_not_private")
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)", line)
        if not match:
            raise PilotError("credential_file_syntax")
        name, value = match.groups()
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                raise PilotError("credential_file_syntax")
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].strip()
        if name in values:
            raise PilotError("duplicate_credential_name")
        values[name] = value

    def choose(names, required):
        found = {values[n] for n in names if values.get(n)}
        if len(found) > 1 or (required and not found):
            raise PilotError("credential_names_missing_or_ambiguous")
        return next(iter(found)) if found else None

    base = choose(("LANGFUSE_BASE_URL", "LANGFUSE_HOST", "BASE_URL", "HOST", "host"), False) or HOST
    if base.rstrip("/") != HOST:
        raise PilotError("host_not_allowlisted")
    public = choose(("LANGFUSE_PUBLIC_KEY", "LANGFUSE_PK", "PUBLIC_KEY", "public_key", "pk", "PK"), True)
    secret = choose(("LANGFUSE_SECRET_KEY", "LANGFUSE_SK", "SECRET_KEY", "secret_key", "sk", "SK"), True)
    return base.rstrip("/"), public, secret


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PilotError("redirect_refused")


class Client:
    def __init__(self, config, attempts=4, timeout=45):
        base, public, secret = config
        if base != HOST:
            raise PilotError("host_not_allowlisted")
        if not 1 <= attempts <= 5 or not 1 <= timeout <= 90:
            raise PilotError("invalid_network_bounds")
        self.base = base
        self.authorization = "Basic " + base64.b64encode((public + ":" + secret).encode()).decode()
        self.attempts = attempts
        self.timeout = timeout
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()))
        self.requests = 0
        self.retries = 0
        self.response_receipts = []
        self.pages = []

    def get(self, path, params=None, record=True):
        if not re.fullmatch(r"/api/public/(?:projects|traces|sessions|observations|v2/observations)(?:/[A-Za-z0-9%_.~-]+)?", path):
            raise PilotError("endpoint_not_allowlisted")
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(url, method="GET", headers={
            "Authorization": self.authorization, "Accept": "application/json",
            "User-Agent": "doubleup-local-readonly-pilot/1"})
        for attempt in range(self.attempts):
            try:
                self.requests += 1
                with self.opener.open(request, timeout=self.timeout) as response:
                    if response.geturl() != url:
                        raise PilotError("redirect_refused")
                    body = response.read(MAX_RESPONSE + 1)
                if len(body) > MAX_RESPONSE:
                    raise PilotError("response_size_cap")
                value = json.loads(body)
                if not isinstance(value, dict):
                    raise PilotError("response_schema_invalid")
                if record:
                    self.response_receipts.append({"request_sha256": hashed([path, params]),
                        "body_sha256": digest(body), "body_bytes": len(body)})
                return value
            except urllib.error.HTTPError as exc:
                status = exc.code
                exc.close()  # Never read/log HTTP error bodies (can include raw prompts).
                if status not in (429, 500, 502, 503, 504):
                    raise PilotError("http_status_" + str(status)) from None
                if attempt + 1 == self.attempts:
                    raise PilotError("http_retries_exhausted_" + str(status)) from None
            except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError):
                if attempt + 1 == self.attempts:
                    raise PilotError("network_retries_exhausted") from None
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise PilotError("response_json_invalid") from None
            self.retries += 1
            time.sleep(min(0.5 * 2 ** attempt, 4))
        raise PilotError("network_retries_exhausted")

    def paginated(self, path, params, max_pages=5000):
        """Fail rather than label a capped, drifting or duplicated page complete."""
        if not 1 <= max_pages <= 10000:
            raise PilotError("invalid_page_cap")
        rows, seen = [], set()
        total = None
        cursor = None
        cursors = set()
        page = 1
        while page <= max_pages:
            query = dict(params)
            query["limit"] = 100
            if cursor is not None:
                query["cursor"] = cursor
            else:
                query["page"] = page
            payload = self.get(path, query)
            data = payload.get("data")
            meta = payload.get("meta") or {}
            if not isinstance(data, list) or not isinstance(meta, dict):
                raise PilotError("pagination_schema_invalid")
            current = meta.get("totalItems", meta.get("totalCount"))
            if current is not None:
                if not isinstance(current, int) or current < 0:
                    raise PilotError("pagination_total_invalid")
                if total is not None and total != current:
                    raise PilotError("pagination_total_changed_retry_with_fixed_end")
                total = current
            for row in data:
                if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
                    raise PilotError("pagination_row_id_missing")
                if row["id"] in seen:
                    raise PilotError("pagination_duplicate_id")
                seen.add(row["id"])
                rows.append(row)
            next_cursor = meta.get("nextCursor", payload.get("nextCursor", meta.get("cursor")))
            self.pages.append({"endpoint": path, "query_sha256": hashed(query), "page": page,
                               "returned": len(data), "total": total})
            if total is not None and len(rows) > total:
                raise PilotError("pagination_count_exceeds_total")
            if next_cursor:
                if not isinstance(next_cursor, str) or next_cursor in cursors or not data:
                    raise PilotError("pagination_cursor_cycle")
                cursors.add(next_cursor)
                cursor = next_cursor
            elif cursor is not None:
                if total is not None and len(rows) != total:
                    raise PilotError("pagination_incomplete")
                return rows, {"complete": True, "mode": "cursor", "pages": page,
                              "total": len(rows), "server_total": total}
            elif total is not None and len(rows) == total:
                return rows, {"complete": True, "mode": "page-total", "pages": page,
                              "total": len(rows), "server_total": total}
            elif "nextCursor" in meta or "nextCursor" in payload or "cursor" in meta:
                # V3 observation API uses meta.cursor for the NEXT cursor.
                alternate = meta.get("cursor")
                if alternate:
                    if not isinstance(alternate, str) or alternate in cursors or not data:
                        raise PilotError("pagination_cursor_cycle")
                    cursors.add(alternate)
                    cursor = alternate
                else:
                    if total is not None and len(rows) != total:
                        raise PilotError("pagination_incomplete")
                    return rows, {"complete": True, "mode": "cursor", "pages": page,
                                  "total": len(rows), "server_total": total}
            elif not data:
                # A short legacy page without a total cannot prove completeness.
                raise PilotError("pagination_total_missing_or_incomplete")
            page += 1
        raise PilotError("pagination_cap_incomplete")


def utc(value):
    if not isinstance(value, str):
        raise PilotError("timestamp_missing")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise PilotError("timestamp_invalid") from None
    if parsed.tzinfo is None:
        raise PilotError("timestamp_timezone_missing")
    return parsed.astimezone(dt.timezone.utc)


def iso(value):
    return value.astimezone(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def validate_window(rows, start, end):
    for row in rows:
        timestamp = utc(row.get("timestamp"))
        if not start <= timestamp <= end:
            raise PilotError("server_date_filter_ignored")


def metadata_nodes(value):
    """Only attribution containers, never recurse into user input/output text."""
    stack = [(value, "")]
    while stack:
        node, path = stack.pop()
        if isinstance(node, str) and node.lstrip().startswith("{"):
            try:
                node = json.loads(node)
            except json.JSONDecodeError:
                continue
        if not isinstance(node, dict):
            continue
        yield node, path
        for key in ("metadata", "attributes", "resourceAttributes", "resource_attributes",
                    "spend_logs_metadata", "traceMetadata"):
            if key in node:
                stack.append((node[key], path + "/" + key))


def attribution(trace):
    tenants, agents, dialogs = {}, {}, {}
    containers = [({"metadata": trace.get("metadata")}, "")]
    for field in ("observations", "pilot_observations_list"):
        observations = trace.get(field)
        if isinstance(observations, list):
            for index, observation in enumerate(observations):
                if isinstance(observation, dict):
                    containers.append(({"metadata": observation.get("metadata")}, "/" + field + "/" + str(index)))
    nodes = ((node, prefix + path) for value, prefix in containers for node, path in metadata_nodes(value))
    for node, path in nodes:
        for key in ("org_id", "orgId", "organization_id", "organizationId", "billing_tenant_id", "tenant_id"):
            value = node.get(key)
            if isinstance(value, (str, int)) and str(value):
                tenants.setdefault(str(value), []).append(path + "/" + key)
        for key in ("agent_id", "agentId", "assistant_id", "assistantId", "billing_assistant_id", "agent_name"):
            value = node.get(key)
            if isinstance(value, (str, int)) and str(value):
                agents.setdefault(str(value), []).append(path + "/" + key)
        for key in ("dialog_id", "dialogId", "conversation_id", "billing_dialog_id"):
            value = node.get(key)
            if isinstance(value, (str, int)) and str(value):
                dialogs.setdefault(str(value), []).append(path + "/" + key)
    # userId is intentionally never promoted to tenant: backend=user, gateway=tenant.
    return {"tenant_status": "attributed" if len(tenants) == 1 else "ambiguous" if tenants else "unknown",
            "tenant_id": next(iter(tenants)) if len(tenants) == 1 else None,
            "tenant_evidence": tenants, "agent_evidence": agents, "dialog_evidence": dialogs,
            "user_id_not_tenant": trace.get("userId")}


def trace_group(trace):
    attr = attribution(trace)
    # Session IDs alone can collide across tenants; conflicting/missing identities
    # remain explicitly flagged, never borrowed from another trace's userId.
    session = trace.get("sessionId")
    dialog_ids = sorted(attr["dialog_evidence"])
    if session:
        return "session:" + str(session)
    if len(dialog_ids) == 1:
        # No sessionId: group explicit billing dialog with tenant provenance.
        return "dialog:" + hashed([attr["tenant_id"], dialog_ids[0]])
    return "unscoped-trace:" + trace["id"]
