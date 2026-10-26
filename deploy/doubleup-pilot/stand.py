"""Own and operate only the isolated DoubleUp pilot Compose project.

Secrets never appear in argv, public manifests, or command output. Image build
contexts are immutable snapshots so concurrent engine edits cannot produce an
unidentified halfway-built container.
"""

import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tarfile
import time

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
STATE = HERE / ".state"
WORKTREES = ROOT.parent
PROJECT = "obscura-doubleup-pilot"
PORTS = (18860, 18861, 18862, 18863, 18881, 18850, 18943)


def run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=True, **kwargs)


def private_write(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(content.encode() if isinstance(content, str) else content)


def load_env(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text().splitlines()
                if line and not line.startswith("#"))


def env_text(items: dict[str, str]) -> str:
    if any("\n" in value or "\r" in value for value in items.values()):
        raise ValueError("multiline environment value refused")
    return "".join(f"{name}={value}\n" for name, value in items.items())


def compose(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    config = load_env(STATE / "compose.env")
    files = ["-f", str(HERE / "compose.yml")]
    if config.get("PILOT_GATEWAY_MODE") == "live":
        files.extend(["-f", str(HERE / "compose.live.yml")])
    return run(["docker", "compose", "--env-file", str(STATE / "compose.env"),
                "--project-name", PROJECT, *files, *args], **kwargs)


def prepare() -> None:
    if STATE.exists():
        raise SystemExit("pilot state already exists; preserve it and use build/up/status")
    for port in PORTS:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", port))
    STATE.mkdir(mode=0o700)
    runtime = STATE / "runtime"
    runtime.mkdir(mode=0o700)
    signing = Ed25519PrivateKey.generate()
    private = base64.b64encode(signing.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())).decode()
    public = base64.b64encode(signing.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
    shared = {"gateway": secrets.token_hex(32), "admin": secrets.token_hex(32),
              "license_admin": secrets.token_hex(32), "jwt": secrets.token_hex(32),
              "vault": secrets.token_hex(32), "minio": secrets.token_hex(24)}
    private_write(runtime / "inspection.key", secrets.token_bytes(32))
    private_write(runtime / "browser.json", json.dumps({"user_id": "pilot-owner", "password": secrets.token_urlsafe(24)}))
    private_write(STATE / "credentials.json", json.dumps(shared))
    private_write(STATE / "gateway-config.json", json.dumps({"enabled": False}))
    private_write(STATE / "pricing.json", json.dumps({"source": "https://litellm.inf.2up.dev/model/info", "models": []}))
    (STATE / "ledger").mkdir(mode=0o700)
    sys.path.insert(0, str(ROOT / "prototype"))
    from e2e.certs import generate
    generate(STATE / "certs", "license")
    # The source image runs uid10001; CA private signer was never persisted.
    (STATE / "certs").chmod(0o755)
    (STATE / "certs" / "server.key").chmod(0o600)
    # Only public CA is mounted into the non-root sidecar; its secret key file
    # remains inside the root-run licensing server's directory.
    private_write(STATE / "license.env", env_text({
        "PSEUDEX_SIGNING_KEY": private, "PSEUDEX_LICENSE_ADMIN_TOKEN": shared["license_admin"],
        "PSEUDEX_CANARY_SECRET": secrets.token_hex(32), "PSEUDEX_WATERMARK_SECRET": secrets.token_hex(32),
        "PSEUDEX_LICENSE_CERT": "/certs/server.pem", "PSEUDEX_LICENSE_KEYFILE": "/certs/server.key",
        "PSEUDEX_LEASE_TTL_SECONDS": "86400", "PSEUDEX_GRACE_SECONDS": "172800",
        "PSEUDEX_LOG_RAW_BODY": "", "PSEUDEX_LOG_LEVEL": "WARNING",
    }))
    private_write(STATE / "sidecar.env", env_text({
        "PSEUDEX_LICENSE_URL": "https://license:8443", "PSEUDEX_LICENSE_CA": "/certs/ca.pem",
        "PSEUDEX_LICENSE_KEY": "not-issued-yet", "PSEUDEX_INSTANCE_ID": "doubleup-local-pilot",
        "PSEUDEX_WORKERS": "1", "PSEUDEX_GATEWAY_TOKEN": shared["gateway"],
        "PSEUDEX_ADMIN_TOKEN": shared["admin"], "PSEUDEX_VAULT_KEY": shared["vault"],
        "PSEUDEX_VAULT_ENCRYPTION": "required", "PSEUDEX_UI_PASSWORD": secrets.token_hex(24),
        "PSEUDEX_LOG_LEVEL": "WARNING",
    }))
    backend = {
        "MONGO_URI": "mongodb://mongodb:27017/doubleup_pilot", "MONGO_DB_NAME": "doubleup_pilot",
        "REDIS_URL": "redis://redis:6379/0", "KEYCLOAK_ENABLED": "false",
        "JWT_SECRET_KEY": shared["jwt"], "BACKEND_JWT_SECRET": shared["jwt"],
        "GUARDRAILS_VAULT_KEY": secrets.token_hex(32),
        "ENVIRONMENT": "local", "EXPOSE_API_DOCS": "true", "LANGFUSE_ENABLED": "false",
        "MAX_ENABLED": "false", "ENABLE_USER_TEMPLATE_GRAPHS": "false", "TEMPLATE_USER_ID": "pilot-template-disabled",
        "FRONTEND_URL": "http://127.0.0.1:18880", "GRAPH_SERVER_URL": "http://graph_server:2024",
        "LOG_LEVEL": "WARNING", "LOG_FORMAT": "json", "LOG_DIR": "/app/logs",
        "QDRANT_URL": "http://qdrant:6333", "QDRANT_API_KEY": "",
        "S3_ENDPOINT_URL": "http://minio:9000", "S3_BUCKET_NAME": "doubleup-pilot",
        "AWS_ACCESS_KEY_ID": "pilot-minio", "AWS_SECRET_ACCESS_KEY": shared["minio"],
        "AWS_DEFAULT_REGION": "us-east-1", "MCP_API_URL": "http://gateway:4000/disabled-mcp",
        "TEXT_EXTRACT_API_URL": "http://gateway:4000/disabled-extract",
        "CHATWOOT_BASE_URL": "http://gateway:4000/disabled-chatwoot", "CHATWOOT_API_TOKEN": "",
        "SEARXNG_URL": "http://gateway:4000/disabled-search", "WHISPERX_API_URL": "http://gateway:4000/disabled-audio",
        "LITELLM_BASE_URL": "http://gateway:4000/v1", "KUBEAI_BASE_URL": "http://gateway:4000/v1",
        "CUSTOM_MODEL_API_BASE": "http://gateway:4000/v1", "CUSTOM_MODEL_API_KEY": "pilot-fixture-no-remote-access",
        "EMBEDDING_API_URL": "http://gateway:4000/v1", "EMBEDDING_API_KEY": "pilot-fixture-no-remote-access",
        "PSEUDEX_PILOT": "1", "PII_BACKEND": "pseudex", "PSEUDEX_BASE_URL": "http://sidecar:8000",
        "OPENAI_API_KEY": "pilot-fixture-no-remote-access", "AWS_EC2_METADATA_DISABLED": "true",
        "PSEUDEX_GATEWAY_TOKEN": shared["gateway"], "PSEUDEX_ADMIN_TOKEN": shared["admin"],
        "PSEUDEX_INSPECTION_KEY_FILE": "/run/pilot/inspection.key",
        "BILLING_AUTHORIZE_ENABLED": "false", "BILLING_EMIT_NONLLM_ENABLED": "false",
        "BILLING_API_URL": "http://gateway:4000/disabled-billing",
        "BILLING_SERVICE_TOKEN": secrets.token_hex(32), "BILLING_ADMISSION_TIMEOUT_SECONDS": "2",
    }
    private_write(STATE / "backend.env", env_text(backend))
    private_write(STATE / "minio.env", env_text({"MINIO_ROOT_USER": "pilot-minio", "MINIO_ROOT_PASSWORD": shared["minio"]}))
    private_write(STATE / "compose.env", env_text({"PILOT_BACKEND_DIR": str(WORKTREES / "doubleup-backend-pilot"),
        "PSEUDEX_LICENSE_PUBKEY": public}))
    archive = subprocess.check_output(["git", "archive", "--format=tar", "HEAD", "prototype"], cwd=ROOT)
    baseline = STATE / "baseline"
    baseline.mkdir(mode=0o700)
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        source.extractall(baseline, filter="data")
    revisions = {}
    for label, path in (("obscura", ROOT), ("backend", WORKTREES / "doubleup-backend-pilot"),
                        ("frontend", WORKTREES / "doubleup-frontend-pilot")):
        revisions[label] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()
    private_write(STATE / "manifest.json", json.dumps({"project": PROJECT, "revisions": revisions,
        "baseline_archive_sha256": hashlib.sha256(archive).hexdigest(), "live_budget_usd": 10,
        "paid_calls_enabled": False, "ports": list(PORTS)}, indent=2))
    print(json.dumps({"prepared": True, "project": PROJECT, "revisions": revisions,
                      "paid_calls_enabled": False}, ensure_ascii=False))


def live_mode(enabled: bool) -> None:
    path = STATE / "gateway-config.json"
    config = load_env(STATE / "compose.env")
    if enabled:
        from dotenv import dotenv_values
        from budget import Ledger, load_pricing, quote
        auth_path = (Path.home() / ".config" / "2up" / "deepseek.env") if config.get('PILOT_UPSTREAM_DIRECT') == '1' else (Path.home() / ".config" / "2up" / "litellm.env")
        if auth_path.stat().st_mode & 0o077:
            raise SystemExit("gateway credential file is not private")
        values = dotenv_values(auth_path)
        token = values.get("DEEPSEEK_API_KEY") if config.get('PILOT_UPSTREAM_DIRECT') == '1' else values.get("LITELLM_TOKEN")
        if not isinstance(token, str) or not token:
            raise SystemExit("gateway credential missing")
        pricing = load_pricing(STATE / "pricing.json")
        quote({"model": "deepseek-v4-flash", "messages": [{"role": "user", "content": "budget preflight"}],
               "max_tokens": 1}, pricing)
        summary = Ledger(STATE / "ledger" / "spend.sqlite3").summary()
        if summary["bound_violated"] or float(summary["remaining_usd"]) <= 0:
            raise SystemExit("pilot budget unavailable")
        request_key = secrets.token_hex(32)
        with path.open("w") as handle:
            json.dump({"enabled": True, "model": "deepseek-v4-flash", "request_key": request_key,
                       "upstream_key": token}, handle)
        access = STATE / "runtime" / "model-access.json"
        with access.open("w") as handle:
            json.dump({"request_key": request_key, "gateway_url": "http://gateway:4000/v1"}, handle)
        access.chmod(0o600)
        config["PILOT_GATEWAY_MODE"] = "live"
    else:
        with path.open("w") as handle:
            json.dump({"enabled": False}, handle)
        config["PILOT_GATEWAY_MODE"] = "fixture"
    path.chmod(0o600)
    with (STATE / "compose.env").open("w") as handle:
        handle.write(env_text(config))
    compose(["up", "-d", "gateway"])
    wait_http("http://127.0.0.1:18850/health", {}, 60)
    from budget import LIMIT_NANO
    print(json.dumps({"live_enabled": enabled, "approved_model": "deepseek-v4-flash" if enabled else None,
                      "budget_limit_usd": LIMIT_NANO / 1_000_000_000, "credentials_printed": False}))


def snapshot_engine() -> None:
    prototype = ROOT / "prototype"
    engine = prototype / "pseudex"
    paths = sorted(path for path in engine.rglob("*") if path.is_file()
                   and "__pycache__" not in path.parts and path.name != "_release.py"
                   and not path.name.endswith(".pyc"))
    paths.extend(prototype / name for name in ("Dockerfile", "Dockerfile.nuitka", "entrypoint.sh", "serve_main.py",
        "build_strip_docstrings.py", "build_harden_strings.py", "build_mangle_names.py", "version.txt", "requirements.txt", "pseudexctl"))
    records = {str(path.relative_to(prototype)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    fingerprint = hashlib.sha256(b"readable-source-layout-v3\0" + json.dumps(records, sort_keys=True).encode()).hexdigest()
    target = STATE / ("engine-" + fingerprint[:16])
    if not target.exists():
        target.mkdir(mode=0o700)
        archive = subprocess.check_output(["git", "archive", "--format=tar", "HEAD", "prototype"], cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(archive)) as source:
            source.extractall(target, filter="data")
        for path in paths:
            destination = target / "prototype" / path.relative_to(prototype)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            destination.chmod(0o755 if path.stat().st_mode & 0o111 else 0o644)
        private_write(target / "engine-manifest.json", json.dumps({"sha256": fingerprint, "files": records}, sort_keys=True))
    config = load_env(STATE / "compose.env")
    config["PILOT_ENGINE_CONTEXT"] = str(target / "prototype")
    with (STATE / "compose.env").open("w") as handle:
        handle.write(env_text(config))
    print(json.dumps({"engine_snapshot_sha256": fingerprint, "files": len(records)}))


def wait_http(url: str, headers: dict[str, str], timeout: float) -> None:
    end = time.monotonic() + timeout
    with httpx.Client(timeout=4, trust_env=False) as client:
        while time.monotonic() < end:
            try:
                response = client.get(url, headers=headers)
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(1)
    raise RuntimeError("pilot HTTP readiness deadline exceeded")


def start_base() -> None:
    compose(["up", "-d", "license", "mongodb", "redis", "qdrant", "minio", "gateway", "frontdoor"])
    credentials = json.loads((STATE / "credentials.json").read_text())
    headers = {"Authorization": "Bearer " + credentials["license_admin"]}
    wait_http("http://127.0.0.1:18943/admin/list", headers, 120)
    config = load_env(STATE / "sidecar.env")
    if config["PSEUDEX_LICENSE_KEY"] == "not-issued-yet":
        with httpx.Client(timeout=15, trust_env=False) as client:
            response = client.post("http://127.0.0.1:18943/admin/issue", headers=headers,
                                   json={"org_id": "doubleup-pilot", "plan": "industrial"})
        response.raise_for_status()
        config["PSEUDEX_LICENSE_KEY"] = response.json()["key"]
        path = STATE / "sidecar.env"
        # This generated file is owned by this operator, never a shared checkout.
        with path.open("w") as handle:
            handle.write(env_text(config))
    compose(["up", "-d", "sidecar"])
    wait_http("http://127.0.0.1:18862/health", {}, 180)
    print(json.dumps({"base_ready": True, "sidecar": "http://127.0.0.1:18862", "paid_calls_enabled": False}))


def roundtrip() -> None:
    credentials = json.loads((STATE / "credentials.json").read_text())
    headers = {"Authorization": "Bearer " + credentials["gateway"]}
    original = "Напишите на pilot.person@example.org, телефон +7 916 123-45-67."
    with httpx.Client(timeout=30, trust_env=False) as client:
        masked = client.post("http://127.0.0.1:18862/mask", headers=headers, json={
            "org_id": "doubleup-pilot", "conversation_id": "pilot-deterministic-contract",
            "messages": [{"role": "user", "content": original}],
        })
        masked.raise_for_status()
        content = masked.json()["messages"][0]["content"]
        if content == original or "pilot.person@example.org" in content or "+7 916 123-45-67" in content:
            raise RuntimeError("masking contract failed")
        response = {"choices": [{"index": 0, "message": {"role": "assistant", "content": None,
            "tool_calls": [{"id": "call_fixture", "type": "function", "function": {
                "name": "pilot_echo", "arguments": json.dumps({"text": content}, ensure_ascii=False)}}]}}]}
        restored = client.post("http://127.0.0.1:18862/unmask", headers=headers, json={
            "org_id": "doubleup-pilot", "conversation_id": "pilot-deterministic-contract", "response": response})
        restored.raise_for_status()
        result = restored.json()
        arguments = result["response"]["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
        if json.loads(arguments)["text"] != original or result.get("residual_tokens"):
            raise RuntimeError("tool argument restoration contract failed")
    print(json.dumps({"mask_changed": True, "tool_json_valid": True, "tool_argument_equal": True,
                      "residual_count": 0, "fixture_only": True, "paid_usd": 0}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "snapshot-engine", "build", "build-compiled", "compiled-gate", "base", "apps", "seed", "fixture", "smoke-dry", "smoke-live", "enable-live", "disable-live", "status", "roundtrip"))
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command in ("enable-live", "disable-live"):
        live_mode(args.command == "enable-live")
    elif args.command == "snapshot-engine":
        snapshot_engine()
    elif args.command == "build":
        compose(["build", "license", "sidecar"])
    elif args.command == "build-compiled":
        config = load_env(STATE / "compose.env")
        context = Path(config.get("PILOT_ENGINE_CONTEXT", str(STATE / "baseline" / "prototype")))
        log = STATE / ("compiled-build-" + context.parent.name + ".log")
        descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as output:
            result = subprocess.run(["docker", "build", "--progress=plain", "-f", str(context / "Dockerfile.nuitka"),
                "--build-arg", "PSEUDEX_LICENSE_PUBKEY=" + config["PSEUDEX_LICENSE_PUBKEY"],
                "--build-arg", "NUITKA_JOBS=2", "-t", "obscura-doubleup-engine:compiled-local", str(context)],
                stdout=output, stderr=subprocess.STDOUT, check=False)
        print(json.dumps({"compiled_build_exit": result.returncode}))
        if result.returncode:
            raise SystemExit(result.returncode)
    elif args.command == "compiled-gate":
        compose(["up", "-d", "sidecar_compiled", "compiled_frontdoor"])
        wait_http("http://127.0.0.1:18863/health", {}, 180)
        compose(["exec", "-T", "sidecar_compiled", "sh", "-c",
                 "test ! -d /app/pseudex && test -x /app/pseudex-serve"])
        env = {**os.environ, "PILOT_INSPECTION_URL": "http://127.0.0.1:18863", "PILOT_ENGINE_KIND": "compiled"}
        run([sys.executable, "-B", str(HERE / "http_inspection_gate.py")], env=env)
    elif args.command == "base":
        start_base()
    elif args.command == "apps":
        path = STATE / "backend.env"
        config = load_env(path)
        config.update({"PSEUDEX_BASE_URL": "http://sidecar:8000",
                       "OPENAI_API_KEY": "pilot-fixture-no-remote-access",
                       "AWS_EC2_METADATA_DISABLED": "true",
                       "BILLING_API_URL": "http://gateway:4000/disabled-billing",
                       "BILLING_ADMISSION_TIMEOUT_SECONDS": "2"})
        if not config.get("BILLING_SERVICE_TOKEN"):
            config["BILLING_SERVICE_TOKEN"] = secrets.token_hex(32)
        with path.open("w") as handle:
            handle.write(env_text(config))
        compose(["up", "-d", "graph_server", "user_api"])
        wait_http("http://127.0.0.1:18861/health", {}, 180)
        wait_http("http://127.0.0.1:18860/llm/api/v1/health", {}, 180)
        print(json.dumps({"graph_api_ready": True, "user_api_ready": True, "paid_calls_enabled": False}))
    elif args.command == "seed":
        compose(["exec", "-T", "graph_server", "python", "/opt/pilot/seed.py"])
    elif args.command == "fixture":
        result = compose(["exec", "-T", "graph_server", "python", "-"],
                         input=(HERE / "boundary_fixture.py").read_text(), text=True, capture_output=True)
        report = json.loads(result.stdout.strip().splitlines()[-1])
        path = STATE / "fixture-gate.json"
        with path.open("w") as output:
            json.dump(report, output, indent=2)
        path.chmod(0o600)
        print(json.dumps(report))
    elif args.command in ("smoke-dry", "smoke-live"):
        command = ["exec", "-T", "graph_server", "python", "-", "--revision", "v2"]
        if args.command == "smoke-dry":
            command.append("--dry-run")
            compose(command, input=(HERE / "live_runner.py").read_text(), text=True)
        else:
            from budget import Ledger
            try:
                live_mode(True)
                compose(command, input=(HERE / "live_runner.py").read_text(), text=True)
            finally:
                live_mode(False)
                print(json.dumps({"budget": Ledger(STATE / "ledger" / "spend.sqlite3").summary(),
                                  "live_mode_disabled": True}), flush=True)
    elif args.command == "status":
        compose(["ps"])
    else:
        roundtrip()


if __name__ == "__main__":
    main()
