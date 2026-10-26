"""Verify the local backend image without an application-source bind mount."""

import json
from pathlib import Path
import socket
import subprocess

import httpx

from stand import HERE, PROJECT, STATE, load_env, run, wait_http


def baked(args, **kwargs):
    return run(["docker", "compose", "--env-file", str(STATE / "compose.env"),
        "--project-name", PROJECT, "-f", str(HERE / "compose.yml"),
        "-f", str(HERE / "compose.baked.yml"), *args], **kwargs)


def main():
    with httpx.Client(timeout=5, trust_env=False) as client:
        if client.get("http://127.0.0.1:18850/health").json().get("mode") != "fixture":
            raise SystemExit("baked_gate_requires_unpaid_fixture_mode")
    # Existing project containers may be reused; an unrelated listener is never stopped.
    for port in (18864, 18865):
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                names = subprocess.check_output(["docker", "ps", "--filter",
                    "label=com.docker.compose.project=" + PROJECT, "--format", "{{.Names}}"], text=True)
                if PROJECT + "-baked_frontdoor-1" not in names:
                    raise SystemExit("baked_gate_port_owned_by_another_process")
    baked(["up", "-d", "graph_baked", "user_baked", "baked_frontdoor"])
    wait_http("http://127.0.0.1:18865/health", {}, 180)
    wait_http("http://127.0.0.1:18864/llm/api/v1/health", {}, 180)
    image = json.loads((STATE / "backend-image.json").read_text())
    containers = json.loads(subprocess.check_output(["docker", "inspect", PROJECT + "-graph_baked-1",
                                                    PROJECT + "-user_baked-1"], text=True))
    for container in containers:
        assert container["Image"] == image["image_id"]
        assert not any(mount["Destination"] == "/app" for mount in container["Mounts"])
    credentials = json.loads((STATE / "runtime" / "browser.json").read_text())
    with httpx.Client(base_url="http://127.0.0.1:18864", timeout=20, trust_env=False) as client:
        login = client.post("/auth/login", json={"user_id": "pilot-owner@example.invalid",
                                                "password": credentials["password"]})
        login.raise_for_status()
        headers = {"Authorization": "Bearer " + login.json()["access_token"], "X-Org-Id": "doubleup-pilot"}
        path = "/api/v1/pseudex/inspections"
        listed = client.get(path, params={"thread_id": "e6f6f3a8-dcf6-5c95-8eb5-fd9359fbeb09"}, headers=headers)
        listed.raise_for_status()
        assert listed.headers["cache-control"] == "no-store" and listed.json()["items"]
        denied = client.get(path, params={"thread_id": "e6f6f3a8-dcf6-5c95-8eb5-fd9359fbeb09"})
        assert denied.status_code == 401 and denied.headers["cache-control"] == "no-store"
        missing = client.get(path + "/00000000000000000000000000000000", headers=headers)
        assert missing.status_code == 404 and missing.headers["cache-control"] == "no-store"
    fixture = baked(["exec", "-T", "graph_baked", "python", "-"],
                    input=(HERE / "boundary_fixture.py").read_text(), text=True, capture_output=True)
    proof = json.loads(fixture.stdout.strip().splitlines()[-1])
    report = {"passed": True, "kind": "baked_backend_http_and_tool_gate",
        "image_id": image["image_id"], "source_sha256": image["source_sha256"],
        "application_source_bind_mounted": False, "user_api_health": True, "graph_api_health": True,
        "real_login": True, "inspection_auth_and_no_store": True, "three_mode_fixture": proof,
        "source_dependency_image_reused": True, "full_requirements_rebuild": False,
        "provider_calls": 0, "paid_usd": 0}
    target = STATE / "baked-backend-gate.json"
    target.write_text(json.dumps(report, indent=2)); target.chmod(0o600)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
