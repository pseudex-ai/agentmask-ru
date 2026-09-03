"""Prometheus text format, written by hand, and the reason is the image.

`prometheus_client` would be a third runtime dependency in both Docker images
for what is string formatting plus an escaping rule. The exposition format is
frozen and four lines long (`# HELP`, `# TYPE`, `name{labels} value`), so the
library would buy a registry we do not want: a global one, populated at import,
which makes two processes of the same binary disagree about what exists.

WHAT THIS IS NOT. There is no in-process aggregation, no histogram and no
summary here. Everything exported is read at scrape time from a place that
already holds it — the licence client, `/proc`, the audit database, the store —
and the one counter that is kept in memory (`Counter`) is kept because HTTP
responses have nowhere else to be counted. That is the whole design: a metric
that is computed twice, once for the screen and once for the scrape, is a metric
that will one day disagree with the screen.

LABELS ARE A CARDINALITY DECISION, NOT A CONVENIENCE. Prometheus keeps one time
series per label combination for ever, so a label whose values come from the
customers — an org id, an instance id, a key — grows the series count with the
business and never shrinks it. `render` therefore takes labels as an explicit
dict and the callers pass constants; the one place that labels by organisation
(`chain_breaks`) does it only for organisations with a non-zero value, because
that set is bounded by trouble rather than by sales.
"""

import threading


def escape(value: str) -> str:
    """Label VALUES may hold any UTF-8, and three characters end the sample.

    A name that arrives with a quote or a newline in it would otherwise produce
    a line Prometheus rejects — and the scrape fails WHOLE, so one bad label
    value takes down every metric in the response, not its own.
    """
    return (value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n"))


def render(name: str, value: float | int | None, help_text: str,
           kind: str = "gauge", labels: dict[str, str] | None = None) -> str:
    """One metric, HELP and TYPE included. `None` renders NOTHING.

    A missing value is not zero and must not be exported as one: «no memory
    limit» exported as `limit_bytes 0` reads on a dashboard as a container with
    no memory, and an alert on `< 512Mi` would fire on every unconstrained
    deployment for ever. Prometheus's own answer to «no data» is an absent
    series, so that is what an absent value produces.
    """
    if value is None:
        return ""
    label_text = ""
    if labels:
        inner = ",".join(f'{key}="{escape(str(text))}"'
                         for key, text in sorted(labels.items()))
        label_text = "{" + inner + "}"
    return (f"# HELP {name} {help_text}\n"
            f"# TYPE {name} {kind}\n"
            f"{name}{label_text} {value}\n")


def series(name: str, samples: dict, help_text: str,
           label: str | tuple[str, ...], kind: str = "gauge") -> str:
    """Several samples of ONE metric, sharing one HELP/TYPE header.

    Repeating the header per sample is what a naive loop over `render` does, and
    Prometheus treats the second header for the same name as a duplicate and
    fails the scrape.

    `label` may name SEVERAL dimensions, and then each key is a tuple. That is
    not generality for its own sake: HTTP outcomes are a path AND a status code,
    and squeezing both into one label value forces every alert to match them
    with a regex over a string somebody formatted — `{route=~"/v1/lease (402|403)"}`
    instead of `{path="/v1/lease", code=~"40[23]"}`. The first breaks the day the
    separator changes and cannot be aggregated by either dimension alone.
    """
    if not samples:
        return ""
    names = (label,) if isinstance(label, str) else tuple(label)
    lines = [f"# HELP {name} {help_text}", f"# TYPE {name} {kind}"]
    for key, value in sorted(samples.items()):
        parts = (key,) if isinstance(key, str) else tuple(key)
        if len(parts) != len(names):
            raise ValueError(f"{name}: {len(names)} labels declared, key {key!r} has {len(parts)}")
        rendered = ",".join(f'{n}="{escape(str(v))}"' for n, v in zip(names, parts))
        lines.append(f"{name}{{{rendered}}} {value}")
    return "\n".join(lines) + "\n"


class Counter:
    """Monotonic counts of things that happen in HTTP handlers.

    Process-local and lost on restart, which is CORRECT for a Prometheus
    counter: `rate()` and `increase()` are defined over resets, and the scrape
    of a restarted process is supposed to show one. What would be wrong is
    persisting it — the number would then survive a rollback and describe a
    binary that is no longer running.

    Locked because uvicorn's loop is one thread but `anyio.to_thread` offloads
    are not, and a lost increment on a billing-adjacent counter is exactly the
    kind of error nobody can reproduce later.
    """

    def __init__(self) -> None:
        self._counts: dict = {}
        self._lock = threading.Lock()

    def add(self, key, amount: int = 1) -> None:
        with self._lock:
            self._counts[key] = self._counts.get(key, 0) + amount

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._counts)
