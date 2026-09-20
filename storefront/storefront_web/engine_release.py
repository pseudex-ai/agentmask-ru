"""Which image the site tells a customer to run (D-061).

`current_image()` answers with the floating MINOR of the newest cycle in the
versions registry — `cr.yandex/…/pseudex:0.3` — read from the copy the deploy
agent syncs after a cosign check (`deploy/agent.sh::sync_registry`). The same
file the licence server judges versions by, so the two cannot disagree.

Order of truth:
  1. `PSEUDEX_DOCKER_IMAGE` set → shown as is (a manual override, nothing else);
  2. the registry file → `<repo>:<newest cycle>`;
  3. no file, or a file that does not parse → `<repo>:latest`, and a log line.

The third case is deliberate: the landing page must render with the registry
missing (a fresh host before the first sync), and `latest` is the one alias
the pipeline always moves with the newest cycle. It is never silent — the log
names the reason.

The file is re-read when its mtime changes, once per request at most; the
agent replaces it atomically, so a half-written file is never seen.
"""

import json
import logging
import os
import threading

from django.conf import settings

_log = logging.getLogger("storefront.engine_release")
_lock = threading.Lock()
_cache: dict[str, object] = {"stamp": None, "cycle": None}


def _newest_cycle(path: str) -> str | None:
    with open(path, encoding="utf-8") as handle:
        doc = json.load(handle)
    cycles = doc.get("cycles")
    if not isinstance(cycles, list) or not cycles:
        raise ValueError("registry has no cycles")
    cycle = cycles[0].get("cycle")
    if not isinstance(cycle, str) or not cycle:
        raise ValueError("newest cycle has no name")
    return cycle


def newest_cycle() -> str | None:
    """The newest cycle («0.3») from the registry, or None when there is no
    usable registry. Cached by the file's mtime and inode."""
    path = str(getattr(settings, "RELEASES_FILE", "") or "")
    if not path:
        return None
    try:
        info = os.stat(path)
        stamp: tuple[int, int, int] | None = (info.st_ino, info.st_mtime_ns, info.st_size)
    except OSError:
        stamp = None
    with _lock:
        if stamp == _cache["stamp"]:
            return _cache["cycle"]  # type: ignore[return-value]
        _cache["stamp"] = stamp
        if stamp is None:
            _cache["cycle"] = None
            _log.warning("versions registry missing at %s — advertising the `latest` alias", path)
            return None
        try:
            _cache["cycle"] = _newest_cycle(path)
        except (OSError, ValueError) as error:
            _cache["cycle"] = None
            _log.warning("versions registry unreadable at %s (%s) — advertising the `latest` alias", path, error)
        return _cache["cycle"]  # type: ignore[return-value]


def current_image() -> str:
    override = str(getattr(settings, "DOCKER_IMAGE", "") or "")
    if override:
        return override
    repo = str(getattr(settings, "DOCKER_IMAGE_REPO", "") or "cr.yandex/pseudex/pseudex")
    cycle = newest_cycle()
    return f"{repo}:{cycle}" if cycle else f"{repo}:latest"
