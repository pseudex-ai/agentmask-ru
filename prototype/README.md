# Veilgate — prototype

Reversible PII tokenization for LLM agents. Real personal data is replaced with
format-preserving fake tokens before the model sees anything; the agent's tool
calls are detokenized server-side, so **the tools still run on real values**.

Two deployment shapes over one core:

| | `veilgate.proxy` | `veilgate.service` (sidecar) |
|---|---|---|
| Who calls the provider | Veilgate | the host gateway |
| Auth | `sk-vg-…` key → tenant → upstream URL + key | `org_id` in the body |
| Surface | `POST /v1/chat/completions` | `/mask`, `/unmask`, `/spans`, `/reveal` |
| Streaming | yes | not yet |

## The engine ships empty

`veilgate/` holds the detection RULES. The tuned data those rules consume — 28k
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
     -d '{"org_id":"acme"}'                          # -> vg_live_...

# 2. the sidecar, in the customer's contour
docker build --build-arg VEILGATE_LICENSE_PUBKEY=<our public key> -t veilgate:source .
docker run -p 8000:8000 -v veilgate-data:/data \
  -e VEILGATE_LICENSE_URL=https://license.example \
  -e VEILGATE_LICENSE_KEY=vg_live_... veilgate:source
```

Without a valid key the container does not start. If the lease stops renewing it
keeps working for the grace window, warns in the log, and then returns 503 —
`GET /license` shows exactly where it is in that ladder.

## Tests and gates

No pytest: every test and eval is a script with a `main()`.

```bash
python3 test_loop.py             # the core proof
python3 test_product.py          # tenancy, audit, streaming detok
python3 test_coverage_152fz.py   # 23 personal-data types, both directions
python3 vault_test.py            # canonicalization + persistence across restart
python3 test_perf_masking.py     # cache, audit de-dup, leak regression, responsiveness

python3 e2e/gates.py             # L1-L15 licensing, against real containers
python3 e2e/pack_gates.py        # P1-P8 packaging, source vs compiled parity
```

Detection quality needs generated datasets (gitignored — regenerate first):

```bash
python3 make_dirty.py && python3 eval_dirty.py
python3 bench/eval_external_ner.py <NEREL corpus>    # the only non-circular recall number
```

## Where the numbers stand

- 0 leaks on the dirty set; 0 of 12 hard negatives falsely masked
- 23/23 personal-data types caught and typed correctly, 7/7 look-alikes untouched
- 80.6% PERSON recall on NEREL — externally annotated, so this is the honest one.
  The remaining misses are foreign celebrities, out of scope for RU business traffic.
- Agent-level damage on BFCL v3 multi-turn (n=200): Δ +2.5 pp, McNemar p=0.560 —
  not distinguishable from the model's own run-to-run variance
