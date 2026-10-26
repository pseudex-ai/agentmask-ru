"""Seed only the guarded, disposable local pilot database; never a shared DB."""

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
            "system_prompt": "Вы помощник локального тестового стенда.", "tools": [], "default_tools": [],
            "retrieval": {"enabled": False}, "kb_tools": False, "updated_at": now}
        db.graphs.update_one({"graph_id": GRAPH}, {"$set": graph, "$setOnInsert": {"created_at": now}}, upsert=True)
        db.threads.update_one({"thread_id": THREAD}, {"$setOnInsert": {"thread_id": THREAD, "user_id": USER,
            "org_id": ORG, "graph_id": GRAPH, "title": "Локальная проверка маскирования", "status": "active",
            "created_at": now, "last_activity": now, "updated_at": now, "message_count": 0}}, upsert=True)
        db.llm_providers.update_one({"provider_id": "pilot"}, {"$set": {"provider_id": "pilot",
            "name": "Local pilot model fixture", "category": "cloud_api", "base_url": "http://gateway:4000/v1",
            "api_type": "openai", "status": "active", "authentication": {"type": "api_key", "required": True,
                "api_key": "pilot-fixture-no-remote-access", "header_name": "Authorization", "prefix": "Bearer"}}}, upsert=True)
        db.llm_models.update_one({"model_id": "pilot/deepseek-v4-flash"}, {"$set": {
            "model_id": "pilot/deepseek-v4-flash", "provider_id": "pilot", "model_name": "deepseek-v4-flash",
            "base_url": "http://gateway:4000/v1", "model_type": "chat", "status": "active",
            "context_length": 128000, "api_type": "openai"}}, upsert=True)
    print(json.dumps({"seeded_local_only": True, "org_id": ORG, "user_id": USER,
                      "graph_id": GRAPH, "thread_id": THREAD, "password_printed": False}))


if __name__ == "__main__":
    main()
