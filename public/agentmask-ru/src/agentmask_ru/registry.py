"""Which maskers the CLI can run, and what each one needs.

An adapter that cannot be built — its library is not installed, its proxy
is not running — fails LOUDLY with what is missing. A benchmark that
silently skips a system it could not reach publishes a leaderboard with a
hole in it and no mark where the hole is.
"""

import argparse

from agentmask_ru.adapters.base import Masker
from agentmask_ru.adapters.openai_proxy import ProxyMasker
from agentmask_ru.adapters.reference import NoopMasker, PlaceholderMasker
from agentmask_ru.upstream import FakeUpstream

ADAPTERS: tuple[str, ...] = ("noop", "placeholder_regex", "openai_proxy", "presidio", "llm_guard", "pseudex_sidecar")


def build(args: argparse.Namespace) -> tuple[Masker, FakeUpstream | None]:
    if args.adapter == "noop":
        return NoopMasker(), None
    if args.adapter == "placeholder_regex":
        return PlaceholderMasker(), None
    if args.adapter == "openai_proxy":
        if not args.base_url:
            raise SystemExit("--base-url is required for openai_proxy")
        host, _, port = args.upstream_bind.partition(":")
        upstream = FakeUpstream(host or "127.0.0.1", int(port or 0))
        upstream.start()
        masker = ProxyMasker(
            name=args.name or "openai_proxy", base_url=args.base_url, upstream=upstream,
            api_key=args.api_key, model=args.model, timeout=args.timeout,
        )
        return masker, upstream
    if args.adapter == "presidio":
        from agentmask_ru.adapters.presidio import PresidioMasker  # imported here: heavy optional dependency

        return PresidioMasker(language=args.language), None
    if args.adapter == "llm_guard":
        from agentmask_ru.adapters.llm_guard import LLMGuardMasker

        return LLMGuardMasker(), None
    if args.adapter == "pseudex_sidecar":
        from agentmask_ru.adapters.pseudex_sidecar import PseudexSidecarMasker

        if not args.base_url:
            raise SystemExit("--base-url is required for pseudex_sidecar")
        return PseudexSidecarMasker(base_url=args.base_url, token=args.api_key, org_id=args.org_id,
                                    name=args.name or "pseudex_sidecar", timeout=args.timeout), None
    raise SystemExit(f"unknown adapter {args.adapter}")
