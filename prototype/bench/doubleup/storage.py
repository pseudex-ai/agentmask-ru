"""No plaintext evidence ever touches disk; manifests contain only counts/hashes.

The persistent key lives in ignored state, outside the immutable evidence runs.
Archive run directories only, NEVER .pilot-state itself (which contains the key).
Filesystem immutability here means exclusive creation + read-only files, not WORM
against the owner/root; the authenticated manifest and SHA256 chain detect edits.
"""

import hashlib
import json
import os
import re
import stat
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PACKAGE = Path(__file__).resolve().parent
STATE = PACKAGE / ".pilot-state"
MAGIC = b"DOUBLEUP-AESGCM-1\n"


class PilotError(Exception):
    """Only constant, non-sensitive codes may cross the CLI boundary."""


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def hashed(value):
    return digest(canonical(value))


def constrained(path):
    path = Path(path).absolute()
    # Reject symlinks even when they currently happen to resolve inside state.
    for part in [path, *path.parents]:
        if part.is_symlink():
            raise PilotError("symlink_refused")
    resolved = path.resolve()
    if not resolved.is_relative_to(STATE.resolve()):
        raise PilotError("write_outside_pilot_state_refused")
    return resolved


def private_dir(path):
    path = constrained(path)
    if not path.exists():
        if path != STATE:
            private_dir(path.parent)
        path.mkdir(mode=0o700)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700:
        raise PilotError("directory_not_private")
    if info.st_uid != os.getuid():
        raise PilotError("directory_owner_mismatch")
    return path


def immutable_write(path, data):
    path = constrained(path)
    private_dir(path.parent)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError:
        raise PilotError("immutable_file_exists") from None
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
        os.fchmod(stream.fileno(), 0o400)


def check_private_file(path, mode):
    path = constrained(path)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != mode:
        raise PilotError("file_not_private_or_immutable")
    if info.st_uid != os.getuid() or info.st_nlink != 1:
        raise PilotError("file_owner_or_link_mismatch")
    return path


def load_key(create):
    private_dir(STATE)
    key_path = constrained(STATE / "corpus.key")
    if not key_path.exists():
        if not create:
            raise PilotError("persistent_key_missing")
        fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(AESGCM.generate_key(bit_length=256))
            stream.flush()
            os.fsync(stream.fileno())
    key = check_private_file(key_path, 0o600).read_bytes()
    if len(key) != 32:
        raise PilotError("invalid_key_length")
    return key


def seal(key, plain, context):
    nonce = os.urandom(12)
    return MAGIC + nonce + AESGCM(key).encrypt(nonce, plain, context.encode("ascii"))


def unseal(key, data, context):
    if not data.startswith(MAGIC):
        raise PilotError("encrypted_header_invalid")
    body = data[len(MAGIC):]
    try:
        return AESGCM(key).decrypt(body[:12], body[12:], context.encode("ascii"))
    except (InvalidTag, ValueError):
        raise PilotError("encrypted_authentication_failed") from None


class RunStore:
    """Exclusive, append-only run writer; only fixed/sanitized filenames accepted."""

    def __init__(self, run_id, create):
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,90}", run_id):
            raise PilotError("invalid_run_id")
        self.run_id = run_id
        self.path = constrained(STATE / "runs" / run_id)
        if create:
            if self.path.exists():
                raise PilotError("immutable_run_exists")
            self.key = load_key(True)
            private_dir(self.path)
        else:
            self.key = load_key(False)
            if not self.path.is_dir():
                raise PilotError("run_missing")
            private_dir(self.path)
        self.entries = []

    def encrypt(self, name, value):
        if not re.fullmatch(r"[a-z0-9-]+\.aesgcm", name):
            raise PilotError("invalid_artifact_name")
        plain = canonical(value)
        context = self.run_id + "/" + name
        cipher = seal(self.key, plain, context)
        immutable_write(self.path / name, cipher)
        entry = {"file": name, "sha256": digest(cipher), "bytes": len(cipher),
                 "plaintext_sha256": digest(plain), "plaintext_bytes": len(plain)}
        self.entries.append(entry)
        return entry

    def finish(self, manifest):
        # Hashes of source code identify the exact normalizer without git mutation.
        manifest["implementation_sha256"] = {
            p.name: digest(p.read_bytes()) for p in sorted(PACKAGE.glob("*.py"))
        }
        manifest["format"] = "doubleup-pilot-v1"
        manifest["run_id"] = self.run_id
        manifest["key_sha256"] = digest(self.key)
        manifest["artifacts"] = self.entries
        # GCM authenticates a copy of the public count/hash manifest, too.
        encoded = canonical(manifest)
        immutable_write(self.path / "manifest.aesgcm", seal(self.key, encoded,
                        self.run_id + "/manifest.json"))
        immutable_write(self.path / "manifest.json", encoded)
        immutable_write(self.path / "manifest.sha256", (digest(encoded) + "\n").encode())
        return manifest

    def verify(self):
        path = check_private_file(self.path / "manifest.json", 0o400)
        encoded = path.read_bytes()
        expected = check_private_file(self.path / "manifest.sha256", 0o400).read_text().strip()
        if digest(encoded) != expected:
            raise PilotError("manifest_hash_mismatch")
        authenticated = unseal(self.key,
            check_private_file(self.path / "manifest.aesgcm", 0o400).read_bytes(),
            self.run_id + "/manifest.json")
        if authenticated != encoded:
            raise PilotError("manifest_authentication_mismatch")
        manifest = json.loads(encoded)
        if manifest["run_id"] != self.run_id or manifest["key_sha256"] != digest(self.key):
            raise PilotError("manifest_identity_mismatch")
        for entry in manifest["artifacts"]:
            name = entry["file"]
            if not re.fullmatch(r"[a-z0-9-]+\.aesgcm", name):
                raise PilotError("invalid_artifact_name")
            cipher = check_private_file(self.path / name, 0o400).read_bytes()
            if digest(cipher) != entry["sha256"] or len(cipher) != entry["bytes"]:
                raise PilotError("artifact_hash_mismatch")
            plain = unseal(self.key, cipher, self.run_id + "/" + name)
            if digest(plain) != entry["plaintext_sha256"] or len(plain) != entry["plaintext_bytes"]:
                raise PilotError("plaintext_hash_mismatch")
        return manifest

    def read_encrypted(self, name):
        return json.loads(unseal(self.key,
            check_private_file(self.path / name, 0o400).read_bytes(), self.run_id + "/" + name))
