"""Bake reviewed backend source into a local image without customer runtime data.

The dependency image is the same one used by the running ARM development stand.
Only the committed baseline plus changed Python files enter the context; no bind
mount, test corpus, credentials, logs or unrelated dirty documentation are copied.
This is a local verification artifact, never a customer/dev/prod image push.
"""

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

from stand import ROOT, STATE, WORKTREES, private_write

BASE = "2up-aiplatform-backend-user_api:latest"
TAG = "obscura-doubleup-backend:local"


def command(args, directory):
    return subprocess.check_output(args, cwd=directory)


def main():
    backend = WORKTREES / "doubleup-backend-pilot"
    base_id = command(["docker", "image", "inspect", BASE, "--format", "{{.Id}}"], ROOT).decode().strip()
    revision = command(["git", "rev-parse", "HEAD"], backend).decode().strip()
    changed = set(command(["git", "diff", "--name-only", "HEAD", "--", "*.py"], backend).decode().splitlines())
    changed.update(command(["git", "ls-files", "--others", "--exclude-standard", "--", "*.py"], backend).decode().splitlines())
    records = {}
    for name in sorted(changed):
        path = backend / name
        if not path.resolve().is_relative_to(backend.resolve()) or not path.is_file() or path.is_symlink():
            raise SystemExit("backend_overlay_path_refused")
        records[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    identity = {"revision": revision, "dependency_image_id": base_id, "overlays": records,
                "artifact_layout": "clean-app-v3-owned"}
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    target = STATE / ("backend-" + fingerprint[:16])
    if not target.exists():
        target.mkdir(mode=0o700)
        archive = command(["git", "archive", "--format=tar", "HEAD"], backend)
        with tarfile.open(fileobj=io.BytesIO(archive)) as source:
            source.extractall(target, filter="data")
        for name in records:
            source = backend / name
            destination = target / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            destination.chmod(0o755 if source.stat().st_mode & 0o111 else 0o644)
        private_write(target / "Dockerfile.pilot", "\n".join([
            "FROM " + BASE, "USER root", "WORKDIR /",
            # The dependency image also contains an OLD /app. COPY cannot
            # remove obsolete modules/tests, so clear only this verified image
            # directory before laying down the exact current source snapshot.
            "RUN python -c \"import pathlib,shutil,sys; p=pathlib.Path('/app'); assert p.resolve()==p and not p.is_symlink() and not pathlib.Path(sys.executable).resolve().is_relative_to(p); shutil.rmtree(p); p.mkdir()\"",
            "WORKDIR /app", "COPY --chown=1000:1000 . /app", "RUN chown 1000:1000 /app",
            'LABEL org.opencontainers.image.revision="' + revision + '"',
            'LABEL org.obscura.pilot.source_sha256="' + fingerprint + '"', "USER 1000", ""]))
        private_write(target / "pilot-source-manifest.json", json.dumps(identity, sort_keys=True))
    log = STATE / ("backend-build-" + fingerprint[:16] + ".log")
    descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as output:
        result = subprocess.run(["docker", "build", "--pull=false", "-f", str(target / "Dockerfile.pilot"),
            "-t", TAG, str(target)], stdout=output, stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)
    image_id = command(["docker", "image", "inspect", TAG, "--format", "{{.Id}}"], ROOT).decode().strip()
    report = {"image": TAG, "image_id": image_id, "source_sha256": fingerprint,
              "baseline_revision": revision, "dependency_image_id": base_id,
              "reviewed_python_overlay_files": len(records), "runtime_data_in_context": False,
              "unrelated_dirty_docs_included": False, "pushed": False}
    path = STATE / "backend-image.json"
    path.write_text(json.dumps(report, indent=2)); path.chmod(0o600)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
