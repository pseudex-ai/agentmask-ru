# Second-wave NAME restoration: candidate provenance, whole identities and fragments

Status: implementation + preliminary offline checks, NOT owner-required live acceptance. No production or original-run writes.

## Fixed candidate/type confusion

Seed2 of the original NAME suite fails on BOTH a810bf8 and the first-wave repair:
`Записать Льва Юдина на15:00` -> `Записать Никиты Никиту Гущина:00`.

A NAME word followed by a number is deliberately offered as a possible address framing. The fallback then allowed that PLACE-only window (`Юдина на15`) to resolve via a NAME part, consuming the clock before the legitimate full name could resolve.

Address-only candidate provenance is now retained through lookup/fallback: a PLACE window cannot be resolved as NAME. Legitimate name windows and LOC fragments remain available. [Red witness](<NAME-TIME-RED.log>); deterministic seed2 now passes.

## Fixed whole-name versus unrelated exact subtoken priority

Controlled legacy rows (legitimate existing-store situation): `ISO` -> `ARTUR`; `Букин Сергей` -> `Ершов Артур`. The uniquely aligned derived full name `ERSHOV ARTUR` correctly resolves to BUKIN SERGEI, but the old replacement ordering applied the single exact ARTUR -> ISO first, yielding ERSHOV ISO.

Resolved spans now retain whether identity came from a complete key/verified derivation, versus a residual-fragment guess. A coherent bound multiword NAME can take its whole range before a shorter unrelated token; guessed partial windows cannot gain priority merely by length. An exact whole literal still wins. Standalone ARTUR retains its original ISO meaning in the test; no global remapping.

[Red witness](<NAME-LATIN-RED.log>). This fixes the demonstrated restoration mechanism, not every source of cross-script mint collisions; preventing future script-blind token-part collisions remains open.

## Full Latin names must have full candidate windows

The Cyrillic scanner offered1–4word names but the Latin path only1–2. With full fake `Котова Карина Валерьевна` plus legitimate split-field aliases, `Kotova Karina Valerevna` restored as mixed-script `Соколова Anna Igorevna`.

Latin now offers the same complete1–4word windows. Identity is still proved by key/alignment, not inferred from mere adjacency. [Deterministic red witness](<LATIN-THREE-RED.log>). Full Latin/role and foreign-text negative tests pass.

## A residual index hit does not license a NAME fragment

The index contains squeezed initials ПО for `Фролов Платон Олегович`; the ordinary tool-text word `по` previously resolved via the residual fallback to the ENTIRE real person. The fallback now requires every surface word to align to an actual fake NAME part. Explicit dotted/squeezed initials still use their separate derivation path; unrelated prose stays prose.

[Red witness](<INITIALS-WORD-RED.log>). Positive tests include full name, given+patronymic, dotted initials and surname+squeezed initials.

## Preliminary checks and open scope

20 cross-hop checks pass. Original17-suite battery after-name-fragments exits0 for every suite, including NAME and derived forms. These are preliminary only; more seeded/randomized comparisons, external/whole-corpus measurements, remaining NAME mint/role/initials/form edge classes, partial numeric forms, streaming and harness fixes remain. Final proof remains new LIVE deepseek-flash C/C′/I on frozen case inputs against original run.
