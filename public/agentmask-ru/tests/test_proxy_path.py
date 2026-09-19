"""The proxy path must measure what the direct path measures."""

from pathlib import Path

from agentmask_ru.adapters.openai_proxy import ProxyMasker
from agentmask_ru.adapters.reference import PlaceholderMasker
from agentmask_ru.harness import run
from agentmask_ru.schema import load_dir
from agentmask_ru.score import score
from agentmask_ru.upstream import FakeUpstream
from tests.reference_proxy import ReferenceProxy

CASES = Path(__file__).resolve().parents[1] / "cases"


def test_proxy_and_direct_agree() -> None:
    cases = load_dir(CASES)[:40]
    direct = score(run(PlaceholderMasker(), cases, "copier", 1))

    upstream = FakeUpstream("127.0.0.1", 0)
    upstream.start()
    proxy = ReferenceProxy(upstream.base_url)
    proxy.start()
    try:
        masker = ProxyMasker(
            name="reference_proxy", base_url=proxy.base_url, upstream=upstream,
            api_key="unused", model="fake", timeout=30.0,
        )
        through_http = score(run(masker, cases, "copier", 1))
    finally:
        proxy.stop()
        upstream.stop()

    # A proxy answers with restored text and never exposes typed spans, so
    # the typed line is absent through HTTP — and that is the ONLY line that
    # may differ. Everything the benchmark publishes about protection and
    # about the round trip must be identical.
    assert set(direct.lines) - set(through_http.lines) == {"typed"}
    for key, line in direct.lines.items():
        if key == "typed":
            continue
        other = through_http.lines[key]
        assert (line.hits, line.total) == (other.hits, other.total), (
            f"{key}: direct {line.hits}/{line.total} but through the proxy {other.hits}/{other.total}"
        )
    assert through_http.errors == 0
    assert upstream.requests >= len(cases)
