"""A2 (extract-once-run-forever) is closed: the tuning rides in the lease, never
in the binary, and no static key opens it offline.

Written BEFORE the implementation, on purpose (ТЗ docs/tz-tuning-in-lease.md): a
gate that is written after the code it guards tends to encode what the code does
rather than what it must do. These assertions describe the TARGET state, so this
file is RED against the compiled-in-blob design and GREEN once the tuning moves
into the lease.

No container, no build — seconds. The build-time counterpart (the shipped image
carries no tuning material at all) lives in `e2e/pack_gates.py` P2/P11/P12.

Run:  python3 test_tuning_lease_security.py
"""
import sys
import zlib
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))


# ── STRUCTURAL: the engine has no offline path to the tuning ──────────────────
# Anti-cheat: these read the SOURCE, so a stale generated `_tuning_blob.py` on
# disk cannot make a functional test lie. The property is "the engine does not
# USE a compiled blob or a static key", which is exactly what the source says.

def test_no_compiled_blob_consumer() -> None:
    """`pseudex/assets.py` must not import or read a compiled tuning blob, and
    must not pop a static `tuning_key` out of the lease. That pair is the whole
    A2 mechanism: static key (in every lease) + ciphertext blob (in the binary)."""
    src = (_HERE / "pseudex" / "assets.py").read_text()
    forbidden = {
        "imports _tuning_blob": "_tuning_blob" in src,
        "calls _load_embedded_tuning": "_load_embedded_tuning" in src,
        "opens a sealed blob": "open_tuning" in src,
        "pops a static tuning_key": 'pop("tuning_key"' in src or "pop('tuning_key'" in src,
    }
    hit = [k for k, v in forbidden.items() if v]
    check(not hit, "engine has no compiled-blob / static-key path",
          f"still present: {hit}" if hit else "assets.py is clean")


def test_bundle_has_no_tuning_seal() -> None:
    """`seal_tuning`/`open_tuning` existed only to seal the compiled blob. With
    the tuning in the lease (already age-sealed + nonce-wrapped) they are dead
    code, and dead crypto is a liability — remove them."""
    src = (_HERE / "pseudex" / "bundle.py").read_text()
    present = [n for n in ("def seal_tuning", "def open_tuning") if n in src]
    check(not present, "no dead tuning-seal primitives in bundle.py",
          f"still defined: {present}" if present else "removed")


def test_no_static_tuning_key_anywhere_in_engine() -> None:
    """No module under `pseudex/` may consume a static `PSEUDEX_TUNING_KEY`: the
    engine must have no key that opens tuning without a live lease."""
    hits = []
    for p in (_HERE / "pseudex").rglob("*.py"):
        if "PSEUDEX_TUNING_KEY" in p.read_text():
            hits.append(p.name)
    check(not hits, "no static PSEUDEX_TUNING_KEY consumer under pseudex/",
          f"found in: {hits}" if hits else "none")


def test_a2_offline_attack_is_dead() -> None:
    """The exact A2 attack: import the compiled blob and decrypt it with a static
    key, from the package alone, no lease. It must be IMPOSSIBLE by construction —
    the module does not exist. (Reproduces research/2026-09-14-security-redteam A2.)

    A stale generated file could still sit on disk; what must be gone is the
    engine's DEPENDENCE on it (tested above) and the shipping of it (pack_gates
    P2/P11). Here we assert the source tree tracks no such module and testkit
    does not regenerate one."""
    testkit_src = (_HERE / "testkit.py").read_text()
    regenerated = "emit_tuning_module" in testkit_src
    pack_src = (_HERE / "licensing" / "pack.py").read_text()
    emits = "def emit_tuning_module" in pack_src
    check(not regenerated and not emits,
          "nothing emits a compiled tuning blob",
          f"testkit_emits={regenerated} pack_emits={emits}")


# ── FUNCTIONAL: the lease carries the tuning; no lease → no detection ──────────

def test_lease_carries_the_tuning() -> None:
    """The bundle the lease delivers must contain the authored tuning — priority
    table, look-alike folds, address apparatus, cue words — not just bulk. That
    is the whole point: the secret travels in the ephemeral, revocable lease."""
    from licensing.pack import build_plaintext
    payload = _decompress_bundle(build_plaintext())
    have = {
        "priority": bool(payload.get("priority")),
        "lookalike": bool(payload.get("lookalike")),
        "address.patterns": bool((payload.get("address") or {}).get("patterns")),
        "context (cue words)": bool(payload.get("context")),
    }
    missing = [k for k, v in have.items() if not v]
    check(not missing, "lease bundle carries the authored tuning",
          f"missing sections: {missing}" if missing else f"sections: {sorted(payload)}")


def test_lease_bundle_has_no_static_key_field() -> None:
    """The lease must not carry a `tuning_key` field: there is no compiled blob
    to open, so shipping a static key in every lease is exactly the leak."""
    from licensing.pack import build_plaintext
    payload = _decompress_bundle(build_plaintext())
    check("tuning_key" not in payload, "lease carries no static tuning_key field",
          f"unexpected keys: {[k for k in payload if 'key' in k.lower()]}")


def test_load_bearing_no_lease_no_detection() -> None:
    """An engine that never leased has NO tuning and refuses to detect. This is
    the anti-patch property, and it must survive the change (it gets stronger:
    there is nothing compiled in to fall back to)."""
    from pseudex.assets import Assets, BundleNotLeased
    a = Assets()
    try:
        a.get()
        check(False, "fresh engine refuses detection (BundleNotLeased)", "get() did not raise")
    except BundleNotLeased:
        check(True, "fresh engine refuses detection (BundleNotLeased)")
    except Exception as exc:  # noqa: BLE001
        check(False, "fresh engine refuses detection (BundleNotLeased)", f"wrong error: {exc!r}")


def test_leased_engine_detects() -> None:
    """With the lease loaded, detection works — regression guard that the new
    load path assembles the same runtime structures."""
    from pseudex.assets import Assets
    from licensing.pack import build_plaintext
    a = Assets()
    a.load(build_plaintext())
    assets = a.get()
    ok = bool(getattr(assets, "priority", None)) and bool(getattr(assets, "names", None))
    check(ok, "leased engine assembles detection assets",
          "priority+names present" if ok else "assets incomplete")


def test_unload_returns_to_refusing() -> None:
    """After unload the engine refuses again — the revocation path still lands in
    fail-closed, which is what makes a short lease actually revoke."""
    from pseudex.assets import Assets, BundleNotLeased
    from licensing.pack import build_plaintext
    a = Assets()
    a.load(build_plaintext())
    a.unload()
    try:
        a.get()
        check(False, "unload returns engine to refusing", "get() did not raise")
    except BundleNotLeased:
        check(True, "unload returns engine to refusing")


def _decompress_bundle(blob: bytes) -> dict:
    # The lease is now sectioned-framed (pseudex.bundle), not one zlib(JSON) blob.
    from pseudex import bundle
    return bundle.unframe_payload(blob)


def main() -> None:
    # Structural first: they read source and cannot be fooled by a stale artifact.
    test_no_compiled_blob_consumer()
    test_bundle_has_no_tuning_seal()
    test_no_static_tuning_key_anywhere_in_engine()
    test_a2_offline_attack_is_dead()
    # Functional.
    test_lease_carries_the_tuning()
    test_lease_bundle_has_no_static_key_field()
    test_load_bearing_no_lease_no_detection()
    test_leased_engine_detects()
    test_unload_returns_to_refusing()

    failed = [name for ok, name, _ in RESULTS if not ok]
    print("=" * 64)
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    if failed:
        print("A2 NOT yet closed — red:", failed)
        raise SystemExit(1)
    print("A2 closed: tuning in the lease, no offline path from the binary.")


if __name__ == "__main__":
    main()
