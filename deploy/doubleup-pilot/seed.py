"""Seed only the guarded, disposable local pilot database; never a shared DB.

ONE ORG, FIVE AGENT IDENTITIES. The pilot has no org axis on purpose: a policy is
chosen per agent, and `agent_id` is what the engine attributes a request to. The
five tester accounts exist so five Playwright sessions can talk to five agents at
once without sharing a thread, and they all belong to the same organisation —
that is the shape the owner asked for, not an oversight.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

from pymongo import MongoClient

from services.auth_service import hash_password

ORG = "doubleup-pilot"
USER = "pilot-owner"
GRAPH = str(uuid5(NAMESPACE_URL, "obscura-doubleup-pilot/graph"))
THREAD = str(uuid5(NAMESPACE_URL, "obscura-doubleup-pilot/thread"))

# Five parallel manual testers. Each gets its own user, graph and thread inside
# the SAME org, so their conversations cannot see each other's vault rows while
# every one of them is still attributed by `agent_id` (the graph id).
TESTERS = 5

# The deterministic CRM the report has to exercise: a real phone resolves, a
# substitute does not. They are gated to the isolated stand inside the registry.
MOCK_TOOLS = ["pseudex_mock_find_contact", "pseudex_mock_get_deal", "pseudex_mock_create_task"]


def _tester(index: int) -> dict:
    suffix = f"tester-{index}"
    return {
        "user_id": f"pilot-{suffix}",
        "graph_id": str(uuid5(NAMESPACE_URL, f"obscura-doubleup-pilot/{suffix}/graph")),
        "thread_id": str(uuid5(NAMESPACE_URL, f"obscura-doubleup-pilot/{suffix}/thread")),
        "name": f"Тестировщик {index}",
        "graph_name": f"Диалог тестировщика {index}",
    }


def main() -> None:
    uri = os.environ.get("MONGO_URI", "")
    parsed = urlsplit(uri)
    if (os.getenv("PSEUDEX_PILOT") != "1" or parsed.scheme != "mongodb"
            or parsed.hostname != "mongodb" or parsed.path != "/doubleup_pilot"
            or os.getenv("MONGO_DB_NAME") != "doubleup_pilot"):
        raise SystemExit("refusing to seed anything except the isolated pilot DB")
    credentials = json.loads(Path("/run/pilot/browser.json").read_text())
    password = credentials["password"]
    if not isinstance(password, str) or len(password) < 20:
        raise SystemExit("private local browser credentials required")
    # THE SEED MUST NOT CLOBBER THE LIVE GATEWAY KEY. `stand.py enable-live`
    # writes the per-run request_key to /run/pilot/model-access.json; the seed
    # runs after it and used to rewrite the provider back to the fixture
    # placeholder, so the next chat answered 401 «Provider rejected pilot».
    live_access = Path("/run/pilot/model-access.json")
    if live_access.exists():
        api_key = json.loads(live_access.read_text()).get("request_key") or ""
        if not isinstance(api_key, str) or len(api_key) < 20:
            raise SystemExit("live model access file is not readable")
    else:
        api_key = "pilot-fixture-no-remote-access"
    with MongoClient(uri, serverSelectionTimeoutMS=5000) as client:
        db = client.get_database()
        now = datetime.now(timezone.utc)
        user = {"user_id": USER, "email": "pilot-owner@example.invalid", "name": "Локальный пилот",
            "org_id": ORG, "permissions": ["user", "pay_user"], "is_active": True,
            "password_hash": hash_password(password), "integrations": {"enabled": False, "providers": {}},
            "onboarding": {"tour_completed": True, "hints_dismissed": ["simple_chat"]}, "updated_at": now}
        db.users.update_one({"user_id": USER}, {"$set": user, "$setOnInsert": {"created_at": now}}, upsert=True)
        db.organizations.update_one({"org_id": ORG}, {"$set": {"org_id": ORG, "name": "DoubleUp · локальный пилот",
            "slug": "doubleup-pilot", "owner_id": USER, "status": "active", "updated_at": now},
            "$setOnInsert": {"created_at": now}}, upsert=True)
        db.organization_members.update_one({"org_id": ORG, "user_id": USER}, {"$set": {
            "org_id": ORG, "user_id": USER, "role": "owner", "status": "active", "updated_at": now},
            "$setOnInsert": {"created_at": now}}, upsert=True)
        graph = {"graph_id": GRAPH, "builtin_id": "simple_chat", "type": "builtin", "enabled": True,
            "name": "Проверка границы данных", "description": "Изолированный локальный пилот. Внешние действия отключены.",
            "user_id": USER, "org_id": ORG, "public": False, "security_level": 3,
            "model_id": "pilot/deepseek-v4-flash", "ai_model": "pilot/deepseek-v4-flash",
            "model_name": "pilot/deepseek-v4-flash", "prompt": "Вы помощник локального тестового стенда.",
            "system_prompt": "Вы помощник локального тестового стенда.", "tools": MOCK_TOOLS, "default_tools": MOCK_TOOLS,
            "retrieval": {"enabled": False}, "kb_tools": False, "updated_at": now}
        db.graphs.update_one({"graph_id": GRAPH}, {"$set": graph, "$setOnInsert": {"created_at": now}}, upsert=True)
        db.threads.update_one({"thread_id": THREAD}, {"$setOnInsert": {"thread_id": THREAD, "user_id": USER,
            "org_id": ORG, "graph_id": GRAPH, "title": "Локальная проверка маскирования", "status": "active",
            "created_at": now, "last_activity": now, "updated_at": now, "message_count": 0}}, upsert=True)
        db.llm_providers.update_one({"provider_id": "pilot"}, {"$set": {"provider_id": "pilot",
            "name": "Local pilot model fixture", "category": "cloud_api", "base_url": "http://gateway:4000/v1",
            "api_type": "openai", "status": "active", "authentication": {"type": "api_key", "required": True,
                "api_key": api_key, "header_name": "Authorization", "prefix": "Bearer"}}}, upsert=True)
        db.llm_models.update_one({"model_id": "pilot/deepseek-v4-flash"}, {"$set": {
            "model_id": "pilot/deepseek-v4-flash", "provider_id": "pilot", "model_name": "deepseek-v4-flash",
            "base_url": "http://gateway:4000/v1", "model_type": "chat", "status": "active",
            "context_length": 128000, "api_type": "openai"}}, upsert=True)

        for index in range(1, TESTERS + 1):
            row = _tester(index)
            db.users.update_one({"user_id": row["user_id"]}, {"$set": {
                "user_id": row["user_id"], "email": f"{row['user_id']}@example.invalid",
                "name": row["name"], "org_id": ORG, "permissions": ["user", "pay_user"],
                "is_active": True, "password_hash": hash_password(password),
                "integrations": {"enabled": False, "providers": {}},
                "onboarding": {"tour_completed": True, "hints_dismissed": ["simple_chat"]},
                "updated_at": now}, "$setOnInsert": {"created_at": now}}, upsert=True)
            db.organization_members.update_one({"org_id": ORG, "user_id": row["user_id"]}, {"$set": {
                "org_id": ORG, "user_id": row["user_id"], "role": "member", "status": "active",
                "updated_at": now}, "$setOnInsert": {"created_at": now}}, upsert=True)
            db.graphs.update_one({"graph_id": row["graph_id"]}, {"$set": {
                "graph_id": row["graph_id"], "builtin_id": "simple_chat", "type": "builtin", "enabled": True,
                "name": row["graph_name"],
                "description": "Изолированный локальный пилот. Внешние действия отключены.",
                "user_id": row["user_id"], "org_id": ORG, "public": False,
                "model_id": "pilot/deepseek-v4-flash", "ai_model": "pilot/deepseek-v4-flash",
                "model_name": "pilot/deepseek-v4-flash",
                "prompt": "Вы помощник локального тестового стенда.",
                "system_prompt": "Вы помощник локального тестового стенда.",
                "tools": MOCK_TOOLS, "default_tools": MOCK_TOOLS, "retrieval": {"enabled": False},
                "kb_tools": False, "updated_at": now}, "$setOnInsert": {"created_at": now}}, upsert=True)
            db.threads.update_one({"thread_id": row["thread_id"]}, {"$setOnInsert": {
                "thread_id": row["thread_id"], "user_id": row["user_id"], "org_id": ORG,
                "graph_id": row["graph_id"], "title": row["graph_name"], "status": "active",
                "created_at": now, "last_activity": now, "updated_at": now, "message_count": 0}}, upsert=True)

    print(json.dumps({"seeded_local_only": True, "org_id": ORG, "user_id": USER,
                      "graph_id": GRAPH, "thread_id": THREAD,
                      "testers": [_tester(index) for index in range(1, TESTERS + 1)],
                      "password_printed": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
