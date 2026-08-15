"""Self-signed CA + server certificate for the stand.

The lease travels over TLS in production, and `PSEUDEX_LICENSE_CA` is a real code
path in the client. Running the stand over plain HTTP would leave that path
untested, so the stand issues its own CA and the sidecar is given it.

Generated with `cryptography`, which is already a dependency — no openssl binary
required, so the stand comes up the same way on any machine.
"""

import datetime
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

_VALID_DAYS = 30


def _write(path: Path, data: bytes) -> None:
    path.write_bytes(data)
    path.chmod(0o644)


def generate(out_dir: Path, hostname: str) -> tuple[Path, Path, Path]:
    """Create ca.pem, server.pem, server.key. Returns their paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    ca_path = out_dir / "ca.pem"
    cert_path = out_dir / "server.pem"
    key_path = out_dir / "server.key"

    # Naive UTC on purpose: x509 validity is UTC by definition and the aware
    # variants of these fields are deprecated in cryptography's API.
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "pseudex-e2e-ca")])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=_VALID_DAYS))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )

    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    server_cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)]))
        .issuer_name(ca_name)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=_VALID_DAYS))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(hostname), x509.DNSName("localhost")]),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )

    _write(ca_path, ca_cert.public_bytes(serialization.Encoding.PEM))
    _write(cert_path, server_cert.public_bytes(serialization.Encoding.PEM))
    _write(key_path, server_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ))
    return ca_path, cert_path, key_path
