"""Credentials: API keys, tokens, private keys — self-anchored, no entropy.

WHY THIS IS NOT AN ENTROPY DETECTOR, which is the whole design.

The obvious way to find secrets is Shannon entropy: a random-looking string is
probably a key. It is also how a masking gateway starts corrupting text it was
never meant to touch. A git SHA, a UUID, a content hash, a base64 image chunk and
minified JavaScript are all high-entropy, none of them are secrets, and an agent
that gets its commit hash rewritten cannot do its job. Over-masking is not the
safe side of this particular trade: it is a silent break in someone's toolchain.

So every pattern here is anchored to a PUBLISHED prefix — `sk-ant-`, `ghp_`,
`AKIA`, `-----BEGIN`. A string matches because the vendor stamped it, not because
it looked random. That gives near-zero false positives at the cost of missing
credentials with no distinguishing shape, and that trade is deliberate: a missed
key is the status quo, a corrupted commit hash is a regression.

The formats are PUBLISHED (vendor documentation, and the open rule sets of
gitleaks/detect-secrets/trufflehog), so by the split rule in CLAUDE.md they live
in the engine, not in the leased bundle. What is leased is the priority entry —
like every other type.

WHY SECRET OUTRANKS EVERYTHING. A Slack token contains a long digit run, and
libphonenumber will happily read a phone number out of the middle of it. A JWT
body is base64 that can hold anything. If a lower-priority recogniser wins a
sub-span of a credential, the credential is cut in half and the halves leak. The
priority table therefore gives SECRET the top slot — above the checksum IDs.

Module is NOT called `secrets.py` on purpose: `vault.py` imports the stdlib
`secrets` for its CSPRNG, and a same-named module in the package shadows it.
"""

import re

from pseudex.detect import Span

# Each entry: (name, compiled pattern). The name is informational — every match
# is typed SECRET, because the customer's question is "did a credential leak",
# not "which vendor issued it". Keeping one type also keeps the vault simple:
# one fake shape family, one priority slot.
#
# Every pattern is written with an explicit length. An open-ended `[A-Za-z0-9]+`
# would swallow whatever follows the key — including the next word of a sentence
# — and the masked span would then eat real text.
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # --- model providers, the ones our own customers hold ----------------
    ("anthropic", re.compile(r"\bsk-ant-(?:api|admin)\d{2}-[A-Za-z0-9_\-]{80,120}")),
    ("openai-project", re.compile(r"\bsk-proj-[A-Za-z0-9_\-]{40,200}")),
    ("openai-service", re.compile(r"\bsk-svcacct-[A-Za-z0-9_\-]{40,200}")),
    ("openrouter", re.compile(r"\bsk-or-v1-[a-f0-9]{64}\b")),
    ("openai-legacy", re.compile(r"\bsk-[A-Za-z0-9]{20}T3BlbkFJ[A-Za-z0-9]{20}\b")),
    ("huggingface", re.compile(r"\bhf_[A-Za-z0-9]{34}\b")),
    # --- clouds -----------------------------------------------------------
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA|AROA|AIDA|ANPA|ANVA)[A-Z0-9]{16}\b")),
    ("google-api-key", re.compile(r"\bAIza[A-Za-z0-9_\-]{35}\b")),
    ("google-oauth", re.compile(r"\bya29\.[A-Za-z0-9_\-]{20,}")),
    ("yandex-oauth", re.compile(r"\by0_[A-Za-z0-9_\-]{20,}")),
    ("yandex-iam", re.compile(r"\bt1\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{86}={0,2}")),
    ("yandex-key-id", re.compile(r"\bYC[A-Za-z0-9_\-]{23}\b")),
    ("yandex-secret", re.compile(r"\bYC[A-Za-z0-9_\-]{38}\b")),
    ("huggingface-org", re.compile(r"\bapi_org_[A-Za-z0-9]{34}\b")),
    # --- code hosting and messaging --------------------------------------
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36}\b")),
    ("github-pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{60,90}\b")),
    ("gitlab-pat", re.compile(r"\bglpat-[A-Za-z0-9_\-]{20}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,90}")),
    ("telegram-bot", re.compile(r"\b\d{8,10}:AA[A-Za-z0-9_\-]{32,33}\b")),
    # --- payments and infrastructure --------------------------------------
    # `sk_` secret and `rk_` restricted only. `pk_` is PUBLISHABLE — Stripe
    # documents it as safe for client-side code, and every mature scanner
    # deliberately does not flag it. Masking it would break the checkout page.
    ("stripe", re.compile(r"\b[sr]k_(?:live|test)_[A-Za-z0-9]{24,99}\b")),
    ("sendgrid", re.compile(r"\bSG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43}\b")),
    ("npm-token", re.compile(r"\bnpm_[A-Za-z0-9]{36}\b")),
    ("pypi-token", re.compile(r"\bpypi-AgEIcHlwaS5vcmc[A-Za-z0-9_\-]{50,}")),
    # --- structural, not vendor-specific ----------------------------------
    # A PEM block is matched whole. Masking only the header would leave the key
    # material in the text, which is the opposite of the point.
    ("private-key", re.compile(
        r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY(?: BLOCK)?-----"
        r"[\s\S]{0,4000}?"
        r"-----END (?:RSA |DSA |EC |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY(?: BLOCK)?-----")),
    # `eyJ` is base64url for `{"`, so a JWT header is self-identifying. Requiring
    # all three dot-separated segments keeps ordinary base64 out.
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}")),
)


# A placeholder is not a credential. `sk-ant-api03-${ANTHROPIC_KEY}`,
# `ghp_xxxxxxxxxxxx` and `sk-live-YOUR_KEY_HERE` appear in documentation, error
# messages and the agent's own config templates. Masking them replaces an
# instruction with a random string, and there was never anything to protect.
_PLACEHOLDER = re.compile(
    r"(?i)(\$\{|\{\{|<|%\()|xxxx|placeholder|your[_\-]?(key|token|secret)"
    r"|example|changeme|replace[_\-]?me|\.\.\.|_here\b")


def detect_credentials(text: str) -> list[Span]:
    """Find credentials by their published prefix. Never by entropy."""
    spans: list[Span] = []
    for _name, pattern in _PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(0)
            if _PLACEHOLDER.search(value):
                continue
            spans.append(Span(match.start(), match.end(), "SECRET", value))
    return spans


# Prefixes that must survive into the fake. The model reasons about which vendor
# a key belongs to ("use the Anthropic key for this call"), so a substitute that
# changes vendor changes meaning. The BODY is what must not survive.
_PREFIX_RE = re.compile(
    r"^(sk-ant-(?:api|admin)\d{2}-|sk-proj-|sk-svcacct-|sk-or-v1-|sk-|hf_|"
    r"AKIA|ASIA|AROA|AIDA|ANPA|ANVA|AIza|ya29\.|y0_|t1\.|"
    r"gh[pousr]_|github_pat_|glpat-|xox[baprs]-|"
    r"[sprk]k_(?:live|test)_|SG\.|npm_|pypi-|eyJ)")


def secret_prefix(value: str) -> str:
    """The vendor-identifying head of a credential, or empty if it has none."""
    match = _PREFIX_RE.match(value)
    return match.group(0) if match else ""
