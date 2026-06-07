"""Offline tests for the product layer: API-key tenancy + streaming detok."""

import pathlib

from obscura.audit import AuditLog, _preview
from obscura.redact import StreamDetokenizer
from obscura.tenants import Tenants
from obscura.vault import Vault


def test_audit() -> None:
    pathlib.Path("a.db").unlink(missing_ok=True)
    audit = AuditLog("a.db")
    audit.record("acme", "PHONE", "+79185702864", "+79991234567")
    audit.record("acme", "NAME", "Полина Жукова", "Иван Петров")
    assert audit.counts("acme") == {"PHONE": 1, "NAME": 1}
    recent = audit.recent("acme", 10)
    assert len(recent) == 2 and "•" in recent[0]["preview"]
    print(f"audit OK — counts {audit.counts('acme')}; preview '+79991234567' -> '{_preview('+79991234567')}'")
    pathlib.Path("a.db").unlink(missing_ok=True)


def test_tenants() -> None:
    pathlib.Path("t.db").unlink(missing_ok=True)
    tenants = Tenants("t.db")
    key = tenants.issue("acme", "https://api.example/v1", "sk-up-123")
    resolved = tenants.resolve(key)
    assert resolved is not None and resolved.customer_id == "acme"
    assert resolved.upstream_key == "sk-up-123"
    assert tenants.resolve("sk-obsc-wrong") is None
    print(f"tenants OK — issued {key[:14]}…, resolves to {resolved.customer_id}; bad key -> None")
    pathlib.Path("t.db").unlink(missing_ok=True)


def test_stream_detok_split_token() -> None:
    vault = Vault(":memory:", "stream")
    token = vault.tokenize("+7 999 123-45-67", "PHONE")
    real = vault.detokenize(token)
    detok = StreamDetokenizer(vault)
    out = ""
    out += detok.feed("Перезвоню вам на ")
    out += detok.feed(token[:6])           # token split across two chunks
    out += detok.feed(token[6:] + " завтра")
    out += detok.flush()
    print(f"STREAM -> {out!r}")
    assert real in out, "split token was not detokenized"
    assert token not in out, "fake token leaked to user in stream"
    print("stream detok OK — split token restored to real value")


if __name__ == "__main__":
    test_tenants()
    test_stream_detok_split_token()
    test_audit()
