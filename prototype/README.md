# Pseudex — prototype

Reversible PII tokenization for LLM agents. Real personal data is replaced with
format-preserving fake tokens before the model sees anything; the agent's tool
calls are detokenized server-side, so **the tools still run on real values**.

Two deployment shapes over one core:

| | `pseudex.proxy` | `pseudex.service` (sidecar) |
|---|---|---|
| Who calls the provider | Pseudex | the host gateway |
| Auth | `sk-ps-…` key → tenant → upstream URL + key | `org_id` in the body |
| Surface | `POST /v1/chat/completions` | `/mask`, `/unmask`, `/spans`, `/reveal` |
| Streaming | yes | not yet |

## The engine ships empty

`pseudex/` holds the detection RULES. The tuned data those rules consume — 28k
given names, 197k surnames, the street gazetteer, cue words, the overlap priority
table — lives in `licensing/`, never ships, and is leased to a running container
as an encrypted bundle that exists only in memory.

That is why a checkout cannot detect anything on its own: every script builds a
bundle first via `testkit.load_dev_bundle()`. Without one the detector raises
`BundleNotLeased`, deliberately — a gateway detecting with half its gazetteer
leaks silently, which is worse than a stopped service.

See `docs/tz-license-packaging.md`.

## Run the proof (no LLM, no network)

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
python3 test_loop.py
```

Expect a masked message with a fake phone/email, a tool call that detokenizes
back to the real values, and `PASS`.

## Run it for real

```bash
# 1. the licensing server (ours; on a stand it can be local)
python3 -m licensing.devserver                       # :8443 public, :9443 admin
curl -X POST localhost:9443/admin/issue -H 'content-type: application/json' \
     -d '{"org_id":"acme"}'                          # -> ps_live_...

# 2. the sidecar, in the customer's contour
docker build --build-arg PSEUDEX_LICENSE_PUBKEY=<our public key> -t pseudex:source .
docker run -p 8000:8000 -v pseudex-data:/data \
  -e PSEUDEX_LICENSE_URL=https://license.example \
  -e PSEUDEX_LICENSE_KEY=ps_live_... pseudex:source
```

Without a valid key the container does not start. If the lease stops renewing it
keeps working for the grace window, warns in the log, and then returns 503 —
`GET /license` shows exactly where it is in that ladder.

## Tests and gates

No pytest: every test and eval is a script with a `main()`.

```bash
python3 test_loop.py             # the core proof
python3 test_product.py          # tenancy, audit, streaming detok
python3 test_coverage_152fz.py   # 152-ФЗ coverage, both directions
python3 test_preflight.py        # how many workers fit; refuse or lower, never OOM
python3 test_pseudexctl.py       # the ops CLI: doctor verdicts and the rekey proof
python3 vault_test.py            # canonicalization + persistence across restart
python3 test_perf_masking.py     # cache, audit de-dup, leak regression, responsiveness

python3 e2e/gates.py             # L1-L22 licensing, vault and preflight, against real containers
python3 make_dirty.py            # P3 compares the two images on it; without it, it refuses
python3 e2e/pack_gates.py        # P1-P10 packaging, source vs compiled parity
```

Detection quality needs generated datasets (gitignored — regenerate first):

```bash
python3 make_dirty.py && python3 eval_dirty.py
python3 bench/eval_external_ner.py <NEREL corpus>    # the only non-circular recall number
```

## Where the numbers stand

- 0 leaks on the dirty set; 0 of 12 hard negatives falsely masked
- `test_coverage_152fz.py` is the authority on coverage and prints its own
  counts: it asserts 22 cases over 21 types, plus 8 look-alikes that must stay
  untouched. The number
  the PRODUCT claims is **18 types** — that is the customer-facing list on
  `/detection`, and it is deliberately smaller than the engine's internal type
  count. A count with no list is a marketing counter, which is why the site
  publishes the list.
- 91.5% PERSON recall on NEREL (Cyrillic 92.3%) — externally annotated, so this is
  the honest one. It was 80.6% until single-token NER people stopped being thrown
  away for not being in the dictionary; see CLAUDE.md for that change and its cost.
- Agent-level damage on BFCL v3 multi-turn (n=200): Δ +2.5 pp, McNemar p=0.560 —
  not distinguishable from the model's own run-to-run variance
