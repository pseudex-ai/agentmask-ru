# B0 independent read-only gate review — PASS (local/design G1)

## Verdict and boundary

**PASS for B0 preservation and the local source/WIP/run/runtime part of G1.** This permits the already-authorized local design/RED wave; it does **not** certify production comparison, implementation quality, container readiness, a release or deployed CVC support.

`production_digest` remains **NOT_VERIFIED**. This is correctly stated in [SPEC:14–16](<research/quality-sprint-2026-09-30/work/B0/SPEC.md#L14-L16>) and [INPUTS:1013](<research/quality-sprint-2026-09-30/work/B0/INPUTS.json#L1013>). The approved [plan G1](<research/quality-sprint-2026-09-30/SPRINT-PLAN.md#L145>) requires the installed digest **for release-A/B**; the [goal B0 clause](<research/quality-sprint-2026-09-30/GOAL-BRIEF.md#L199-L203>) likewise places production verification before release comparison. RG must remain blocked on that proof. No blanket “all G1/release PASS” is warranted.

Reviewer operated as a separate delegated agent. Requested inherited Lead target is `gpt-6-astra`; self-identity is not technical proof. No network/provider/production call, install, Git mutation, detector scoring or environment change was performed. Only this review file was written. The private archive was **stream-read**, never unpacked into the shared root.

## Inputs actually read

- [SPEC](<research/quality-sprint-2026-09-30/work/B0/SPEC.md>), complete [checkpoint source](<research/quality-sprint-2026-09-30/work/B0/checkpoint.py>) and [checkpoint log](<research/quality-sprint-2026-09-30/work/B0/checkpoint.log>).
- [INPUTS](<research/quality-sprint-2026-09-30/work/B0/INPUTS.json>), [RUNTIME](<research/quality-sprint-2026-09-30/work/B0/RUNTIME.json>) and full machine-parsed [WIP manifest](<research/quality-sprint-2026-09-30/work/B0/WIP-MANIFEST.json>).
- Relevant approved G1/B0 authorization and applicability in [SPRINT-PLAN](<research/quality-sprint-2026-09-30/SPRINT-PLAN.md#L109-L178>) and [GOAL-BRIEF](<research/quality-sprint-2026-09-30/GOAL-BRIEF.md#L199-L203>).
- All recorded archive members/reference files/source pins, the previous88 baseline and17 paid-run original hashes, frozen run corpus/triples and ladder membership, four runtime dictionary files and six installed dependency RECORD inventories.
- [Bundle-builder source](<prototype/licensing/pack.py#L325-L415>) before deterministic **in-memory** bundle reconstruction. No detector, vault or lease server was instantiated.

## Verified results

| Check | Independent result |
|---|---|
| Archive exists and exact file digest | `d94367ac911255558e8f52407d469cd7ed8d311f9a8382cf1589a7be5be2a719` |
| Archive byte size | **21,968,795**, matches checkpoint log |
| Authored WIP/evidence payload members | **441/441** unique members matched manifest byte sizes/SHA256 **and current source SHA256** |
| Total tar members | **443 regular files**:441 payloads + `CHECKPOINT-git-diff.patch` + `CHECKPOINT-git-status.txt`; no duplicate paths, absolute/traversal paths, symlinks or hardlinks |
| Embedded tracked binary patch | Byte-identical to current `git diff --binary HEAD` during review |
| Reference-only files | **3554/3554** current size/SHA256 matches; every file belongs to dependency directories, no tmp/cache-category entries in this snapshot |
| Dependency provenance cross-check | **3548** hashes match installed distribution RECORD entries; **6** unhashed entries are the RECORD files themselves. No unmatched reference path |
| Explicit skipped entries | **0**; no authored-source omission found within checkpoint's Git dirty/untracked census |
| Source/run pins | **198/198** unique paths verified: **181 Python files +17 raw-run files**; canonical source-manifest digest also matches |
| Git identity | HEAD `0bfda2363ef1a1d552e2ac093129b1026a86ad68`; branch `research/hop-format-audit`; v6 ref `fad9c7466ea1221282214e6c747ca373ee7e6a55` all match |
| Prior planning baseline | **88/88** SHA256 match |
| Paid original archive source | **17/17** SHA256 match |
| Paid-run population | **813 unique corpus IDs;802 complete +11 excluded** |
| Holdout | **359 IDs**, run intersection **0**; saved ladder file digest and declared holdout tier digest recompute correctly |
| Runtime | Python3.12.12 string and interpreter resolution match; all7 recorded package versions and4 dictionary file sizes/SHA256 match |
| In-memory bundle | Version `2a07cebae2b050ec`, **1,524,582 bytes**, SHA256 `01c19f4689450b54694b7aaa4070cbaf695efc3e98f0b59471486392a0348206`; byte-identical to runtime record, no bundle file written |

The dependency-reference roots contain755 files under `external/dependencies` and2799 under `supplement/dependencies`. Their installed distributions are pyarrow25.0.1, pandas2.2.3, python-dateutil2.9.0.post0, six1.17.0, pytz2026.4 and tzdata2026.4. Classification is not based only on directory names: RECORD digests independently account for every referenced payload. This is evidence they are reproducible installed dependencies rather than accidentally omitted authored scripts; it is not a promise that remote packages will remain available forever. Their current on-disk copies were not removed.

### Key pending work is in the archive

Each of these paths was explicitly asserted present and hash-matched:

- [M04 prototype](<prototype/bench/agentpii5/answer_restoration.py>) and [M04 tests](<prototype/bench/agentpii5/test_answer_restoration.py>).
- Existing [UI work](<prototype/bench/agentpii5/live.py>) and [run registry update](<prototype/bench/agentpii5/runs.json>).
- [Approved sprint plan](<research/quality-sprint-2026-09-30/SPRINT-PLAN.md>), [full goal contract](<research/quality-sprint-2026-09-30/GOAL-BRIEF.md>), [latest decisions](<research/quality-sprint-2026-09-30/REMAINING-DECISIONS.md>) and [wiki index](<wiki/INDEX.md>).

## One verification failure investigated, not hidden

The first inventory command exited **1** because it asserted that the *current* Git dirty/untracked census was exactly the snapshot census. It found two additional files, no missing original path:

| New path | Filesystem creation UTC | Relation to snapshot |
|---|---|---|
| [SUBAGENT-USAGE](<research/quality-sprint-2026-09-30/work/SUBAGENT-USAGE.md>) | 2026-09-30T19:46:39.250805+00:00 | After snapshot |
| [FIRST-WAVE-SCOPES](<research/quality-sprint-2026-09-30/work/FIRST-WAVE-SCOPES.md>) | 2026-09-30T19:47:55.293309+00:00 | After snapshot |

Snapshot timestamp in INPUTS is **2026-09-30T19:43:31.805599+00:00**. Both files are execution/review coordination documents created later, not unpreserved old WIP. All441 archived sources and all3554 reference hashes still match. The corrected census assertion permits **exactly these two timestamped additions**, not arbitrary differences, and exited0. They are not covered by this earlier archive and should be included in a later checkpoint; this is not a reason to overwrite the immutable B0 snapshot.

## Commands, exits and checked assertions

No review helper was saved outside this file. Commands were inline Python, read-only, with `PYTHONDONTWRITEBYTECODE=1`:

| ID | Invocation / assertions | Exit |
|---|---|---:|
| C1 | `prototype/.venv/bin/python - <<'PY'`: stream `tarfile.open(archive,'r|gz')`; hash all member/source/reference paths; compare full current dirty/untracked census | **1** — exactly the two later additions above; archive/source/reference assertions had passed |
| C2 | Same interpreter, inline stdlib verifier: repeat hashes, enforce443 unique safe regular members, compare embedded patch to `git diff --binary HEAD`, reconcile exactly two later additions using creation+mtime, verify key backups and198 source-manifest pins + Git refs | **0** |
| C3 | Same interpreter, inline stdlib verifier: recompute88 prior/17 paid hashes; raw triples statuses;813 unique IDs; ladder SHA256; holdout359 and SHA256 of newline-joined tier; intersection0 | **0** |
| C4 | From `prototype`, `.venv/bin/python - <<'PY'`: compare `sys.version`, interpreter and `importlib.metadata.version`; hash four dictionaries; `build_payload()` and `build_plaintext()` with default empty org/watermark **in memory only**; compare version/len/SHA256 | **0** |
| C5 | Root interpreter, inline stdlib verifier: load six `.dist-info/RECORD` CSVs, resolve paths, compare base64url SHA256 and sizes to every referenced file; allow only RECORD's own empty digest | **0** |

Important exact verification formulas:

```python
assert hashlib.sha256(json.dumps(inputs['sources'], sort_keys=True).encode()).hexdigest() == inputs['source_manifest_sha256']
assert hashlib.sha256('\n'.join(ladder['tiers']['holdout']).encode()).hexdigest() == ladder['tier_sha256']['holdout']
assert {r['status']: sum(t['status'] == r['status'] for t in triples) for r in triples} == {'complete': 802, 'excluded': 11}
assert len(set(case['base']['id'] for case in corpus)) == 813
assert not (set(case['base']['id'] for case in corpus) & set(ladder['tiers']['holdout']))
```

The checkpoint script was inspected, **not re-executed**: its duplicate-archive refusal is statically present at lines30–31 and avoids overwriting existing evidence. No live mutation test of a second checkpoint was needed for this read-only preservation review.

## Limits that remain explicit

1. This archive preserves Git dirty/untracked authored work and evidence in its recorded scope, not every ignored file on the host or an independent off-machine backup. Dependencies remain hash-referenced. B0's own generated artifacts are intentionally outside its input-WIP archive.
2. Filename filtering is not a universal secret-content audit. The archive is private/local/not-for-publication; do not publish or commit it wholesale. Zero explicit skipped credential paths does not prove every archived byte is non-sensitive.
3. **0/359 membership intersection is not “holdout globally untouched.”** It says only that this paid run's selected IDs do not overlap the pinned tier. Historical access/tuning is not proven absent.
4. In-memory development bundle identity is not the digest of a deployed image. No production access occurred, and RG remains gated on a separately verified installed artifact.
5. No M04, engine, detector, benchmark, container, API, quality, or release implementation gate was tested or accepted here. The28 existing prototype checks are not silently promoted by this B0 review.

**No blocking defect remains for the specified local/design B0 gate.** Parent may record scoped G1 PASS and advance authorized design/RED work; keep production verification and all later owner/quality/release gates open.
