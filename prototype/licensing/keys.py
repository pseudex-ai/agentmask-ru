"""The Ed25519 signing key of the licensing server.

One key, held only by us; its public half is compiled into the customer's binary.
It answers "did Pseudex make this bundle" — see `pseudex/bundle.py` for why that
question is separate from "who may open it".

The private key is loaded from the environment as base64 raw bytes, never from a
file in the image: the licensing server is the one component that runs on our
own infrastructure, so its secret comes from the platform's secret store.

`PSEUDEX_SIGNING_KEY` absent is allowed ONLY for a local stand, where a fresh
ephemeral key is generated and its public half printed — a stand must be
reproducible from nothing. In that mode the server says so loudly, because a
production instance that silently regenerated its key would invalidate every
deployed binary's compiled-in public key at once.
"""

import base64
import hashlib
import logging
import os

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from pseudex.bundle import decode_public_key

_log = logging.getLogger("licensing.keys")

# Re-exported so the server and the tooling have one name for it; the parser
# itself lives in pseudex/bundle.py because the ENGINE needs it and cannot import
# anything from this package.
#
# A second `def decode_public` below this line used to shadow the alias, so the
# comment described one implementation while callers got another — a raw
# `binascii.Error` on a malformed key instead of the BundleError the shared
# parser raises, and two copies free to drift apart. The alias is the only
# definition now.
decode_public = decode_public_key


def encode_private(key: Ed25519PrivateKey) -> str:
    raw = key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    return base64.b64encode(raw).decode("ascii")


def encode_public(key: Ed25519PublicKey) -> str:
    raw = key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    return base64.b64encode(raw).decode("ascii")


def tuning_key_id(tuning_b64: str) -> str:
    """The cache-busting fingerprint of the tuning key: `PSEUDEX_TUNING_KEY_ID`.

    The key itself reaches the image build as a SECRET MOUNT, and BuildKit keeps
    secret contents out of the layer cache on purpose — so a rotated key alone
    hits the cache and ships a blob sealed to the previous key (measured: two
    keys, one blob). This value enters as an ordinary build-arg and busts the
    cache exactly when the key changes; the Dockerfile recomputes it from the
    mounted secret and refuses a mismatch, so a caller cannot pass a stale one.
    Sixteen hex characters of the SHA-256 of a 256-bit random key are not the
    key."""
    return hashlib.sha256(tuning_b64.encode("ascii")).hexdigest()[:16]


def load_signing_key() -> Ed25519PrivateKey:
    encoded = os.environ.get("PSEUDEX_SIGNING_KEY", "")
    if encoded:
        return Ed25519PrivateKey.from_private_bytes(base64.b64decode(encoded))
    key = Ed25519PrivateKey.generate()
    _log.warning(
        "PSEUDEX_SIGNING_KEY is not set — generated an EPHEMERAL signing key. "
        "Every binary compiled against a different public key will reject this "
        "server's leases. Public key: %s", encode_public(key.public_key()),
    )
    return key
