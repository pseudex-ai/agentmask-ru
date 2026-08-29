"""Where the encryption key of the three stores comes from — and why never from us.

The vault is the ONLY place in the product where a real personal value exists in
a durable form. Everything else was built so that no second copy appears: the
audit keeps a preview, the licensing server gets counters. So the key that opens
it is the whole of the protection, and who holds it is a product decision rather
than a configuration detail.

WHY NOT THE LEASE MECHANISM, which already exists and already seals a payload to
one process. Two reasons, and the first is fatal: the vault survives a restart
and a process keypair does not, so a leased key would make every restart a
permanent data loss. The second is worse than a bug — issuing the key from our
licensing server would make US a party able to decrypt Russian citizens' personal
data held by a microfinance company, turn our downtime into their unopenable
vault, and put us into processing-by-instruction territory. The key stays with
the customer.

FOUR SOURCES, IN PRIORITY ORDER, and the third is the one that earns its keep:

  PSEUDEX_VAULT_KEY       64 hex characters (a raw 32-byte key), or any other
                          string, which is then a passphrase run through Scrypt.
  PSEUDEX_VAULT_KEY_FILE  the docker/k8s secrets convention — a mounted file.
  PSEUDEX_VAULT_KEY_CMD   the stdout of any command. Fifteen lines that close
                          Yandex KMS, VK Cloud, HashiCorp Vault and every other
                          secret manager with no integration on our side at all.
  (nothing set)           we generate one BESIDE THE DATABASE and say so out
                          loud, every start. A key next to the data does not
                          protect against volume theft, which is the threat the
                          whole feature exists for; a product that stays quiet
                          about that is lying by omission.

RAW KEY OVER PASSPHRASE, MEASURED. Opening a connection costs 0.08 ms with a raw
key and 67.8 ms when SQLCipher has to run its KDF over a passphrase (this
machine; the spec measured 1.2 / 41.6 on another — the ratio is the point). At
eight workers times three stores that is the difference between a quarter of a
millisecond and two seconds of startup, and the passphrase buys nothing the
operator's own secret manager does not already give.

ONE SECRET, THREE KEYS. `vault.db`, `audit.db` and `tenants.db` get different
keys derived with HKDF-SHA256 under different `info` labels, so a key recovered
from one file does not open the next. `cryptography` is already a dependency —
this adds no package.
"""

import binascii
import logging
import os
import re
import subprocess
import threading

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

# The HKDF `info` labels. They are part of the on-disk format: changing one
# changes the key derived for that store and makes an existing file unopenable,
# so they are versioned and never edited in place.
VAULT_STORE = "pseudex/store/v1/vault"
AUDIT_STORE = "pseudex/store/v1/audit"
TENANTS_STORE = "pseudex/store/v1/tenants"
LICENSING_STORE = "pseudex/store/v1/licensing"

_KEY_FILENAME = "pseudex-vault.key"
_SALT_FILENAME = "pseudex-vault.salt"

# Scrypt cost for the passphrase route. RFC 7914's interactive-login parameters:
# ~100 ms and 32 MB per derivation on ordinary hardware. Deliberately expensive,
# because a passphrase an operator can type is the one input here with little
# entropy — and the cost is paid once per connection, not per query.
_SCRYPT_N = 2 ** 15
_SCRYPT_R = 8
_SCRYPT_P = 1

# Three attempts on the command route, because it is the one source that is a
# call to somebody else's service: a KMS behind a network hiccup must not take
# the container down on the first timeout. The last error is raised, never
# swallowed — a key that cannot be fetched is a refusal to start, not a fallback.
_CMD_ATTEMPTS = 3
_CMD_TIMEOUT_SECONDS = 30

_HEX64 = re.compile(r"\A[0-9a-fA-F]{64}\Z")

_log = logging.getLogger("pseudex.vault_key")


class VaultKeyError(RuntimeError):
    """The key could not be resolved, and the deployment requires one."""


class VaultSecret:
    """The resolved master secret plus where it came from.

    Not a dataclass on purpose: `material` is key material, and a dataclass
    would put it into `__repr__`, which then ends up in a traceback, in a log
    line, and in the customer's log aggregator.
    """

    __slots__ = ("_material", "source", "beside_data")

    def __init__(self, material: bytes, source: str, beside_data: bool) -> None:
        if len(material) != 32:
            raise VaultKeyError(
                f"vault secret must be 32 bytes, got {len(material)} from {source}"
            )
        self._material = material
        self.source = source
        # True when WE generated it next to the database. The single fact the
        # operator has to know, so it is carried rather than re-derived.
        self.beside_data = beside_data

    def __repr__(self) -> str:
        return f"<VaultSecret source={self.source} beside_data={self.beside_data}>"

    def store_key(self, store: str) -> str:
        """The 64-hex key for one store, derived from the master secret."""
        derived = HKDF(
            algorithm=hashes.SHA256(), length=32, salt=None,
            info=store.encode("utf-8"),
        ).derive(self._material)
        return binascii.hexlify(derived).decode("ascii")


# Resolution is cached per data directory: PSEUDEX_VAULT_KEY_CMD may be a call
# to a KMS, and running it on every connection would turn every new org's Vault
# into a network round trip — and every KMS audit log into noise.
_CACHE: dict[str, VaultSecret | None] = {}
_CACHE_LOCK = threading.Lock()


def _mode() -> str:
    """`auto` (default), `required`, or `off`.

    `required` refuses to start unless an EXPLICIT source resolves. It must not
    be satisfied by the generated key, or the setting would be decorative: a
    misconfiguration that lost PSEUDEX_VAULT_KEY_CMD would silently downgrade to
    a key sitting in the stolen volume, which is exactly the state `required`
    exists to forbid.
    """
    # EMPTY IS UNSET. `PSEUDEX_VAULT_ENCRYPTION: "${PSEUDEX_VAULT_ENCRYPTION:-}"`
    # is the ordinary way a compose file passes an optional variable through, and
    # so is a k8s env entry with no value — both arrive as "". Treating that as a
    # bad value refused to start the whole e2e stand on the very first run, with
    # a message about a key on a deployment that had asked for nothing.
    mode = os.environ.get("PSEUDEX_VAULT_ENCRYPTION", "").strip().lower() or "auto"
    if mode not in ("auto", "required", "off"):
        raise VaultKeyError(
            f"PSEUDEX_VAULT_ENCRYPTION={mode!r} is not one of auto, required, off"
        )
    return mode


def _material_from_text(text: str, data_dir: str, source: str) -> bytes:
    """64 hex characters are a key; anything else is a passphrase."""
    if _HEX64.match(text):
        return binascii.unhexlify(text)
    if len(text) < 12:
        raise VaultKeyError(
            f"{source} holds {len(text)} characters. A vault key is either 64 hex "
            f"characters (a raw 32-byte key) or a passphrase of at least 12."
        )
    _log.warning(
        "vault: %s is a passphrase, not a raw key — every connection pays the "
        "Scrypt derivation (~100 ms). 64 hex characters cost 0.1 ms.", source,
    )
    return Scrypt(salt=_salt(data_dir), length=32,
                  n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P).derive(text.encode("utf-8"))


def _salt(data_dir: str) -> bytes:
    """The passphrase salt, stored beside the data and created once.

    A fixed salt compiled into the product would make ONE precomputation work
    against every pseudex deployment in the country. The salt is not a secret, so
    living in the same volume as the data costs nothing — but it must be backed
    up with it: without this file the passphrase no longer opens the vault. The
    key-loss regulation covers both.
    """
    path = os.path.join(data_dir, _SALT_FILENAME)
    try:
        with open(path, "rb") as handle:
            salt = handle.read()
        if len(salt) == 16:
            return salt
        raise VaultKeyError(
            f"{path} is {len(salt)} bytes, expected 16. Restore it from the "
            f"backup taken with the database — a different salt derives a "
            f"different key and the vault will not open."
        )
    except FileNotFoundError:
        pass
    salt = os.urandom(16)
    _write_private(path, salt)
    _log.warning("vault: wrote a new passphrase salt to %s — back it up WITH the "
                 "database; the passphrase alone will not open the vault", path)
    return salt


def _write_private(path: str, payload: bytes) -> None:
    """Create the file readable by its owner only, and never widen an existing one.

    O_EXCL rather than a plain open: two workers starting together would both
    generate, and the loser would overwrite the key the winner had already used
    to encrypt the volume with. The loser reads the winner's file instead.
    """
    try:
        handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return
    try:
        os.write(handle, payload)
        os.fsync(handle)
    finally:
        os.close(handle)


def _from_environment(data_dir: str) -> VaultSecret | None:
    text = os.environ.get("PSEUDEX_VAULT_KEY", "").strip()
    if not text:
        return None
    return VaultSecret(_material_from_text(text, data_dir, "PSEUDEX_VAULT_KEY"),
                       "PSEUDEX_VAULT_KEY", False)


def _from_file(data_dir: str) -> VaultSecret | None:
    path = os.environ.get("PSEUDEX_VAULT_KEY_FILE", "").strip()
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read().strip()
    except OSError as error:
        raise VaultKeyError(
            f"PSEUDEX_VAULT_KEY_FILE={path!r} could not be read: {error}"
        ) from None
    if not text:
        raise VaultKeyError(f"PSEUDEX_VAULT_KEY_FILE={path!r} is empty")
    source = f"PSEUDEX_VAULT_KEY_FILE ({path})"
    return VaultSecret(_material_from_text(text, data_dir, source), source, False)


def _from_command(data_dir: str) -> VaultSecret | None:
    command = os.environ.get("PSEUDEX_VAULT_KEY_CMD", "").strip()
    if not command:
        return None
    # shell=True on purpose. The command is the OPERATOR's own, written into
    # their own deployment, and every real secret manager invocation is a
    # pipeline — `yc kms symmetric-crypto decrypt ... | base64 -d`. Refusing the
    # shell would mean shipping an integration per vendor instead.
    last: Exception | None = None
    for attempt in range(1, _CMD_ATTEMPTS + 1):
        try:
            done = subprocess.run(command, shell=True, capture_output=True,
                                  text=True, timeout=_CMD_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as error:
            last = error
            _log.warning("vault: PSEUDEX_VAULT_KEY_CMD timed out after %ss "
                         "(attempt %d/%d)", _CMD_TIMEOUT_SECONDS, attempt, _CMD_ATTEMPTS)
            continue
        if done.returncode == 0 and done.stdout.strip():
            source = "PSEUDEX_VAULT_KEY_CMD"
            return VaultSecret(_material_from_text(done.stdout.strip(), data_dir, source),
                               source, False)
        # stderr is included because a KMS failure is almost always explained
        # there and almost never by the exit code alone.
        last = VaultKeyError(
            f"PSEUDEX_VAULT_KEY_CMD exited {done.returncode} with "
            f"{len(done.stdout.strip())} bytes on stdout; stderr: "
            f"{done.stderr.strip()[:400] or '(empty)'}"
        )
        _log.warning("vault: PSEUDEX_VAULT_KEY_CMD failed (attempt %d/%d): %s",
                     attempt, _CMD_ATTEMPTS, last)
    raise VaultKeyError(f"PSEUDEX_VAULT_KEY_CMD failed {_CMD_ATTEMPTS} times: {last}")


def _generated(data_dir: str) -> VaultSecret:
    path = os.path.join(data_dir, _KEY_FILENAME)
    if not os.path.exists(path):
        os.makedirs(data_dir, exist_ok=True)
        _write_private(path, binascii.hexlify(os.urandom(32)))
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read().strip()
    if not _HEX64.match(text):
        raise VaultKeyError(
            f"{path} does not hold 64 hex characters. It is the key to this "
            f"volume's vault; if it was edited or truncated, restore it from a "
            f"backup — nothing else opens the data."
        )
    # Said on EVERY start, not once at creation. The operator who inherits this
    # deployment in a year never saw the creation line.
    _log.warning(
        "vault: encrypted with a key generated BESIDE THE DATA (%s). This "
        "protects a copied database file, NOT a stolen volume or backup — both "
        "carry the key. Set PSEUDEX_VAULT_KEY_CMD (a secret manager), "
        "PSEUDEX_VAULT_KEY_FILE or PSEUDEX_VAULT_KEY to hold the key elsewhere.",
        path,
    )
    return VaultSecret(binascii.unhexlify(text), f"generated ({path})", True)


def resolve(data_dir: str) -> VaultSecret | None:
    """The master secret for the stores in `data_dir`, or None when off.

    None means "write plaintext" and is reachable only by setting
    PSEUDEX_VAULT_ENCRYPTION=off explicitly. There is no path where a failure to
    resolve degrades to plaintext — that would be a product claiming encryption
    and silently not doing it.
    """
    data_dir = os.path.abspath(data_dir)
    with _CACHE_LOCK:
        if data_dir in _CACHE:
            return _CACHE[data_dir]
        mode = _mode()
        if mode == "off":
            # Says what is TRUE of any store, not "this holds personal data":
            # the licensing server sets `off` deliberately and holds none, and a
            # warning that overstates its case is one an operator learns to skip
            # — including on the deployment where it is the whole point.
            _log.warning(
                "vault: PSEUDEX_VAULT_ENCRYPTION=off — the stores in %s are "
                "written in plain text. Anyone with the volume, a backup of it "
                "or a snapshot of the host disk reads whatever is in them.",
                data_dir,
            )
            _CACHE[data_dir] = None
            return None
        secret = (_from_environment(data_dir) or _from_file(data_dir)
                  or _from_command(data_dir))
        if secret is None:
            if mode == "required":
                raise VaultKeyError(
                    "PSEUDEX_VAULT_ENCRYPTION=required, but none of "
                    "PSEUDEX_VAULT_KEY, PSEUDEX_VAULT_KEY_FILE or "
                    "PSEUDEX_VAULT_KEY_CMD resolved to a key. Refusing to start: "
                    "generating one beside the data would leave the key in the "
                    "volume this setting exists to protect."
                )
            secret = _generated(data_dir)
        else:
            _log.info("vault: encrypted, key from %s", secret.source)
        _CACHE[data_dir] = secret
        return secret


def replacement(data_dir: str) -> VaultSecret:
    """The secret PSEUDEX_VAULT_KEY_NEW names, for the rekey role.

    Deliberately ONE source and not the four-step ladder above. Rotation is an
    act somebody performs at a keyboard with both keys in front of them, and a
    priority order would mean the new key could quietly come from somewhere the
    operator did not intend — on the one operation where naming the wrong key
    leaves a volume nobody can open.
    """
    text = os.environ.get("PSEUDEX_VAULT_KEY_NEW", "").strip()
    if not text:
        raise VaultKeyError(
            "PSEUDEX_VAULT_KEY_NEW is not set. Rotation needs both keys: the "
            "current one through the usual PSEUDEX_VAULT_KEY* variables, the "
            "replacement here."
        )
    return VaultSecret(_material_from_text(text, data_dir, "PSEUDEX_VAULT_KEY_NEW"),
                       "PSEUDEX_VAULT_KEY_NEW", False)


def key_literal(key_hex: str) -> str:
    """The SQL literal for `PRAGMA key` and `ATTACH ... KEY`, validated first.

    SECURITY-CRITICAL, not a formatting nicety. `PRAGMA key` cannot be
    parameterised — `near "?": syntax error` — so this value is concatenated into
    SQL text, and it is the only place in the product where that happens. There
    is no correct ESCAPING of a key: a string that is not a key is not a key that
    needs quoting, it is a bug or an injection, and both must stop here. So the
    shape is checked and anything else is refused.

    SQLCipher's raw-key form is a string literal holding a blob literal:
    `PRAGMA key = "x'2dd29c...'"`. A bare `'2dd29c...'` would be taken as a
    PASSPHRASE and silently derive a different key — the file would open on
    neither.
    """
    if not _HEX64.match(key_hex):
        raise VaultKeyError(
            f"a store key must be exactly 64 hex characters; refusing to build "
            f"SQL from a {len(key_hex)}-character value"
        )
    return f"\"x'{key_hex}'\""


def state(data_dir: str) -> dict[str, object]:
    """What `/status` reports. Never the key, never anything derived from it."""
    try:
        secret = resolve(data_dir)
    except VaultKeyError as error:
        return {"encrypted": False, "key_source": "unresolved", "error": str(error),
                "key_beside_data": False}
    if secret is None:
        return {"encrypted": False, "key_source": "disabled", "key_beside_data": False}
    return {"encrypted": True, "key_source": secret.source,
            "key_beside_data": secret.beside_data}


def reset_cache() -> None:
    """Forget the resolved secret. For the probe role and for tests that switch
    deployments inside one process; nothing on a request path calls it."""
    with _CACHE_LOCK:
        _CACHE.clear()
