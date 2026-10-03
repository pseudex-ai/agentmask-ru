# First-wave review and preliminary offline measurement

These checks are PRECONDITIONS only. Owner requires final validation by a new LIVE LLM run on the SAME recorded cases with before/after business comparison.

## Independent review

Code-review run576a6caa-3e18-4a59-85ce-5d1447f66c3e found four introduced gaps despite old suite17/17 and first12checks passing:
1. Leaf isolation revalidated DOB with fewer cues and lost supported typo/др/pronoun birth evidence.
2. A twice-shortened address compared a conversation prefix as part of the street and rejected a legitimate alias.
3. Role-aware number fallback protected regex-shaped but unbound numeric tokens, preventing abbreviations д./кв. from restoring.
4. Markdown field support failed to stop before the NEXT Markdown label and swallowed status text.

All four reproduced in [review red log](<REVIEW-RED.log>) before correction. Fixes reuse the actual quasi recognizer inside the correct leaf, separate scope from address identity, protect only resolved token spans, and share label boundary grammar for both plain/Markdown fields. [Sixteen checks now green](<GREEN-reviewed.log>). The after-review17-suite battery completed with16pass/1fail: test_names_morphology found an unrestored inflected fake and a dative mismatch. This failure was NOT waived. Paired8seed before/after runs found the same reproducible time-consuming NAME failure at seed2 in BOTH versions. It is now pinned and repaired in the NAME provenance work; see NAME-PROVENANCE.md. The initial random feminine/dative failures remain separate stress targets, not proven closed by one fixed seed. No release claim.

## Generated corpus comparison

Datasets regenerated ONLY in repair worktree with original deterministic seeds.
Same files evaluated by BOTH source engines, separate processes:
- baseline imports `/Users/igor/Projects/Obscura-v6-integration/prototype` at a810bf8; no write there;
- repair imports current `/Users/igor/Projects/Obscura-agent-integrity/prototype`.

Golden eval_detect: BOTH baseline and repair exit1,298items, overall rounded96%/96%. Exactly12 source DATE labels detected as DOB (DATE recall0%, DOB precision48%). This is a pre-existing type-taxonomy mismatch, not new privacy leakage or proof of pass. Instrument/ground truth reconciliation is pending; no threshold or label weakened here.

Dirty eval_dirty: BOTH exit0,150/150 all-type correct, hard-negative false masks0/12, true leaks0/150.

Earlier full17script baseline and after-ownership/after-field-boundaries/after-compositional-projection all exit0. See each RESULTS.json; these do NOT certify the untested remainder of the repair scope or substitute for the live validation mandate.
