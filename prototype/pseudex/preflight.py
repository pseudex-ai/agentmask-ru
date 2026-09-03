"""How many workers fit in the memory this container was actually given.

WHY THIS IS NOT A COMMENT IN `entrypoint.sh`. It was one — «pick
PSEUDEX_WORKERS so N*300 MB fits the container memory limit with headroom» —
and a comment cannot refuse. What happens instead is that the fan-out starts,
the kernel's OOM killer takes whichever worker asked for a page last, the
supervisor sees a child gone and takes the container down with status 137, and
the operator gets a number that names neither memory nor us. The whole failure
is knowable BEFORE anything starts: the limit is a file, the cost per worker is
measured, and the arithmetic is one division.

WHY PYTHON AND NOT SHELL, given the caller is a shell script. Two readers need
the same answer — `entrypoint.sh` before the fan-out, and `/diagnostics` while
the container runs — and a second implementation in `sh` would be a second
place for the sentinel values below to drift. `serve_main.py` already ships in
both images and already exposes one-shot roles this way (`probe`), so the
entrypoint calls this exactly as it calls that.

THE PER-WORKER NUMBER IS MEASURED, NOT ASSUMED. 350 MB is the resident size of
one worker on the source path with a real bundle leased and the Natasha model
built (7 MB bare interpreter, 117 after the bundle, 252 after importing
`pseudex.service`, 351 after `Detector()`, and flat across sixty detections
after that — morphology allocates its dictionaries once). The interface is a
separate process of the same binary that never imports the engine: 43 MB. Both
are overridable, because a customer's traffic mix is not ours to predict and a
preflight that cannot be argued with becomes a preflight people delete.
"""

import os
import sys

# The measurement above, rounded up to the nearest 10 MB in our own favour.
DEFAULT_WORKER_MB = 350
DEFAULT_UI_MB = 50
# Everything that is not a worker: the shell, the page cache SQLCipher reads
# through, the WAL, and the margin between "fits exactly" and "fits". A budget
# with no slack is how a container survives its first day and dies on its
# second, when one transcript is longer than any we tested.
DEFAULT_HEADROOM_MB = 128

# cgroup v1 writes a sentinel rather than a flag for «no limit» — historically
# 0x7FFFFFFFFFFFF000, but the exact value depends on the page size, so it is
# compared as «absurdly large» rather than matched. v2 writes the literal
# string «max», which needs no threshold.
_UNLIMITED_ABOVE_MB = 1024 * 1024   # 1 TiB


def _read_int(path: str) -> int | None:
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read().strip()
    except OSError:
        return None
    if not text or text == "max":
        return None
    try:
        return int(text)
    except ValueError:
        return None


def memory_limit_mb(root: str = "/sys/fs/cgroup",
                    env: dict[str, str] | None = None) -> int | None:
    """The container's memory ceiling in MB, or None when there is none.

    `root` is a parameter and not a constant because the check that decides
    whether a container starts has to be testable, and a test cannot fake
    `/sys`. It has a second, real use: a nested runtime may mount the hierarchy
    somewhere else, and then the honest answer is «point us at it», not «we
    guessed and refused».

    An explicit `PSEUDEX_MEMORY_LIMIT_MB` wins over both files. Under cgroup v1
    inside some nested setups the file shows the HOST's memory, which would make
    this check pass on a container that has a tenth of it — the operator who
    knows the real number needs a way to say it.
    """
    env = os.environ if env is None else env
    override = env.get("PSEUDEX_MEMORY_LIMIT_MB", "").strip()
    if override:
        value = _megabytes(override)
        if value:
            return value
        # НЕ None: НЕПОНЯТАЯ ПЕРЕМЕННАЯ НЕ ИМЕЕТ ПРАВА ВЫКЛЮЧАТЬ ПРОВЕРКУ.
        # «2g» — это как раз то, что пишут, потому что так пишут в docker; тихо
        # вернув None, мы бы отключили предполёт целиком и объяснили это
        # «cgroup смонтирован иначе», то есть обвинили бы не то. Суффиксы g/m/k
        # понимаются ниже; всё остальное — жалоба и падение обратно на файлы,
        # которые говорят правду.
        print(f"pseudex preflight: PSEUDEX_MEMORY_LIMIT_MB={override!r} не похоже на "
              f"размер памяти (ожидается 2048, 2048m или 2g) — читаем cgroup", file=sys.stderr)

    for relative in ("memory.max",                      # cgroup v2
                     "memory/memory.limit_in_bytes"):   # cgroup v1
        raw = _read_int(os.path.join(root, relative))
        if raw is None or raw <= 0:
            continue
        megabytes = raw // (1024 * 1024)
        if megabytes >= _UNLIMITED_ABOVE_MB:
            continue
        return megabytes
    return None


def plan(limit_mb: int | None, cpus: int,
         env: dict[str, str] | None = None) -> dict[str, object]:
    """Decide how many workers to run, and say why in words the operator gets.

    THE VERDICT DEPENDS ON WHO CHOSE THE NUMBER, and that asymmetry is the whole
    design. A count the operator wrote down is a statement of intent: silently
    running four of their eight would make a deployment that is quietly a
    quarter of the throughput they provisioned for, and nothing would ever say
    so. A count WE derived from `nproc` is our guess, so lowering our own guess
    and saying it loudly is right — refusing to start over it would be refusing
    over an assumption we made ourselves.
    """
    env = os.environ if env is None else env
    worker_mb = _positive(env.get("PSEUDEX_WORKER_MB"), DEFAULT_WORKER_MB)
    headroom_mb = _positive(env.get("PSEUDEX_HEADROOM_MB"), DEFAULT_HEADROOM_MB)
    # `${PSEUDEX_UI:-1}` В ШЕЛЛЕ СЧИТАЕТ ПУСТУЮ СТРОКУ ЕДИНИЦЕЙ, а `.get(…, "1")`
    # возвращает саму пустую строку — и бюджет расходился с тем, что реально
    # запускается: интерфейс стартовал, а память под него не была заложена.
    ui_mb = DEFAULT_UI_MB if (env.get("PSEUDEX_UI") or "1") == "1" else 0

    asked_raw = env.get("PSEUDEX_WORKERS", "").strip()
    explicit = bool(asked_raw)
    asked = _positive(asked_raw, max(1, cpus))

    result: dict[str, object] = {
        "limit_mb": limit_mb, "asked": asked, "explicit": explicit,
        "worker_mb": worker_mb, "ui_mb": ui_mb, "headroom_mb": headroom_mb,
        "need_mb": asked * worker_mb + ui_mb + headroom_mb,
        "workers": asked, "fits": None,
    }
    if limit_mb is None:
        result["verdict"] = "unknown"
        result["reason"] = ("предела памяти не видно (не в контейнере или cgroup "
                            "смонтирован иначе) — проверка пропущена")
        return result

    fits = (limit_mb - ui_mb - headroom_mb) // worker_mb
    result["fits"] = fits
    if fits >= asked:
        result["verdict"] = "ok"
        result["reason"] = (f"{asked}×{worker_mb} МБ + {ui_mb + headroom_mb} МБ "
                            f"укладывается в {limit_mb} МБ")
        return result

    # BELOW ONE WORKER THERE IS NOTHING TO LOWER TO, so this refuses whoever
    # chose the number. Starting a single worker that will be killed mid-request
    # is worse than not starting: the caller fails closed either way, but only
    # one of the two says what to change.
    if fits < 1:
        result["workers"] = 0
        result["verdict"] = "refused"
        result["reason"] = (
            f"в {limit_mb} МБ не помещается НИ ОДИН воркер: одному нужно "
            f"{worker_mb} МБ плюс {ui_mb + headroom_mb} МБ на интерфейс и запас. "
            f"Дайте контейнеру минимум {worker_mb + ui_mb + headroom_mb} МБ")
        return result

    if explicit:
        result["workers"] = 0
        result["verdict"] = "refused"
        result["reason"] = (
            f"PSEUDEX_WORKERS={asked} не помещается в {limit_mb} МБ: нужно "
            f"{result['need_mb']} МБ. Поместится {fits} — либо поставьте "
            f"PSEUDEX_WORKERS={fits}, либо дайте контейнеру "
            f"{result['need_mb']} МБ")
        return result

    result["workers"] = fits
    result["verdict"] = "reduced"
    result["reason"] = (
        f"ядер {cpus}, но в {limit_mb} МБ помещается {fits} воркеров — "
        f"запускаем {fits}. Пропускная способность ниже, чем позволяет CPU; "
        f"поднимите лимит памяти до {result['need_mb']} МБ, чтобы занять все ядра")
    return result


def cpus_available() -> int:
    """Cores this process may actually use, not the machine's.

    `os.cpu_count()` reports the host's cores even when the container is pinned
    to two of them, and a worker count derived from it would be a guess about
    somebody else's machine. Shared by the preflight role and by the live report
    in `operator.py`, so the two cannot answer differently.
    """
    try:
        return len(os.sched_getaffinity(0))
    except AttributeError:                       # not Linux
        return os.cpu_count() or 1


def _megabytes(raw: str) -> int | None:
    """A bare number is MB; g/m/k are honoured because that is how docker spells
    it and the variable is read by the same people who wrote `--memory=2g`."""
    text = raw.strip().lower().rstrip("b")
    # g и m, но не k: лимит памяти контейнера в килобайтах — не конфигурация,
    # которую кто-то пишет, а опечатка, и принять её значило бы округлить её в
    # ноль и отказать со ссылкой на цифру, которой человек не писал.
    scale = {"g": 1024, "m": 1}.get(text[-1:], None)
    if scale is not None:
        text = text[:-1]
    try:
        value = int(text)
    except ValueError:
        return None
    if scale is None:
        scale = 1
    megabytes = value * scale
    return megabytes if megabytes > 0 else None


def _positive(raw: str | None, fallback: int) -> int:
    """A malformed knob falls back rather than raising: this runs before
    anything else in the container, and a traceback here would replace every
    diagnostic below it with a stack trace about `int()`."""
    try:
        value = int((raw or "").strip())
    except ValueError:
        return fallback
    return value if value > 0 else fallback
