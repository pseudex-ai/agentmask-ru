"""M04: raw-first, occurrence-local restoration of delivered answers.

ADD ONLY: no case timetable, old HopObservation or engine code is consulted.
Unknown identity/provenance/alignment stays visible in the candidate population.
Final delivered streaming bytes are `base.reply`, NEVER `reply_whole`.

v2-dev requires explicit provider-linked disclosure evidence before a candidate
can earn success. Legacy spellings nominate candidates only. Exact copied fakes
are checked against the literal source, not a silently repaired canonical.
Initials/role hypotheses without proved mappings remain unresolved. The legacy
capture adapter, derived-role proof, and unique alignment acceptance are OPEN;
this development version must not yet be published as a fully accepted G2 metric.
"""
from collections import Counter
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
from functools import lru_cache
import hashlib
import re
from typing import Sequence

from bench.agentpii4.parts import parts_of
from bench.agentpii5 import contracts
from bench.agentpii5.contracts import CaseV5, ArmRunV5
from bench.agentpii5.form import _ANALYZER, form_match, loc_generic
from bench.agentpii5.observe import value_needles, _needle_spans, values_equal, fold, initials_of

ESTIMATOR_VERSION = 'm04-answer-restoration-2-dev'
WORD = re.compile(r'[A-Za-zА-Яа-яЁё]+(?:-[A-Za-zА-Яа-яЁё]+)*')
STATUSES = ('matched', 'value_wrong', 'form_wrong', 'residual', 'ambiguous',
            'provenance_unavailable', 'alignment_unresolved', 'form_unmeasured')


@lru_cache(maxsize=16384)
def _lemmas(word: str) -> frozenset[str]:
    low = fold(word)
    # A dictionary is evidence of morphology; prefix distance is NOT identity.
    if re.fullmatch(r'[а-яё-]+', low):
        return frozenset([low] + [fold(p.normal_form) for p in _ANALYZER.parse(low)])
    return frozenset((low,))


def _name_equal(left: str, right: str) -> bool:
    a, b = WORD.findall(left), WORD.findall(right)
    if not a or len(a) != len(b):
        return False
    # Small exact bipartite matching; repeated equal words cannot reuse a role.
    def match(i: int, remaining: tuple[int, ...]) -> bool:
        if i == len(a):
            return True
        return any(_lemmas(a[i]) & _lemmas(b[j]) and
                   match(i + 1, tuple(k for k in remaining if k != j)) for j in remaining)
    return match(0, tuple(range(len(b))))


def _equal(kind: str, left: str, right: str) -> bool:
    if kind == 'NAME':
        return _name_equal(left, right)
    if kind == 'LOC' and loc_generic(left) != loc_generic(right):
        # Street TYPE is identity. Keep this additive to M04: the historical
        # shared comparator must not silently change with an answer metric.
        return False
    return values_equal(kind, left, right)


def _squeeze_initials(text: str) -> str:
    """Letter heads of a written initials form, casefolded, dots stripped."""
    return ''.join(c for c in text if c.isalpha()).casefold()


def _initials_value_equal(delivered: str, real: str) -> bool:
    """A written initials form matches SOME rendering of the real name's initials
    (Cyrillic or Latin). Not a full-name comparison."""
    heads = _squeeze_initials(delivered)
    return bool(heads) and heads in initials_of('NAME', real)


@dataclass(frozen=True)
class DisclosureProof:
    """One source-to-fake replacement in a provider-request input capture.

    request uses PROVIDER ordinals, NOT MentionRecord.request_index. The caller
    must read it from an actual linked capture, never zip gateway snapshots to
    responses. Hashes and byte/slot checks validate internal integrity, not an
    external attestation of the caller. Synthetic fixtures state that origin.
    v2-dev only accepts exact whole source slots. Partial/derived proof support
    must not be simulated by expanding the permitted replacement region.
    """
    record_id: str
    request: int
    item_id: str
    source_kind: str                 # message / tool_result
    source_index: int                # message index / recorded call seq
    source_text: str
    masked_text: str
    source_start: int
    source_end: int
    masked_start: int
    masked_end: int
    source_sha256: str
    masked_sha256: str


@dataclass(frozen=True)
class AnswerEvidence:
    disclosures: tuple[DisclosureProof, ...]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def validate_evidence(case: CaseV5, run: ArmRunV5,
                      evidence: AnswerEvidence | None) -> None:
    """Refuse malformed evidence; never count it as a restoration failure."""
    for mention in run.mentions:
        if not 0 <= mention.request_index <= run.request_count:
            raise ValueError('M04: mention push index outside recorded gateway push count')
    if evidence is None:
        return
    if evidence.disclosures and run.model_trace is None:
        raise ValueError('M04: explicit disclosure requires provider chronology')
    responses = {} if run.model_trace is None else {r.request: r for r in run.model_trace.responses}
    if run.model_trace is not None:
        requests=[r.request for r in run.model_trace.responses]
        if (any(type(n) is not int or n < 1 for n in requests)
                or requests != sorted(set(requests))):
            raise ValueError('M04: invalid or non-monotone provider request ordinals')
        if any(type(r.available_results) is not int
               or not 0 <= r.available_results <= len(run.base.calls)
               for r in run.model_trace.responses):
            raise ValueError('M04: provider result boundary must be a whole count within recorded calls')
        cr = run.model_trace.call_requests
        if len(cr) != len(run.base.calls):
            raise ValueError('M04: call_requests must map every accepted call exactly once')
        if any(type(n) is not int or n not in responses for n in cr):
            raise ValueError('M04: call_requests names a missing or non-integer provider request')
    items = {p.id: p for p in case.base.pii}
    seen = set()
    for proof in evidence.disclosures:
        if not proof.record_id or proof.record_id in seen:
            raise ValueError('M04: disclosure record id missing or repeated')
        seen.add(proof.record_id)
        if any(type(n) is not int for n in (proof.request,proof.source_index,proof.source_start,
                                           proof.source_end,proof.masked_start,proof.masked_end)):
            raise ValueError('M04: disclosure ordinals and bounds must be integers, not booleans')
        response = responses.get(proof.request)
        item = items.get(proof.item_id)
        if response is None or item is None:
            raise ValueError('M04: disclosure names an unknown response or item')
        if proof.source_sha256 != _sha(proof.source_text) or proof.masked_sha256 != _sha(proof.masked_text):
            raise ValueError('M04: disclosure payload hash mismatch')
        if not (0 <= proof.source_start < proof.source_end <= len(proof.source_text)
                and 0 <= proof.masked_start < proof.masked_end <= len(proof.masked_text)):
            raise ValueError('M04: disclosure bounds outside payload')
        if proof.source_kind == 'message':
            if not (item.where.kind == 'message' and proof.source_index == item.where.msg
                    and 0 <= proof.source_index < len(case.base.messages)
                    and proof.source_index <= response.turn
                    and proof.source_text == case.base.messages[proof.source_index].content
                    and (proof.source_start, proof.source_end) == (item.where.start, item.where.end)):
                raise ValueError('M04: message disclosure disagrees with original source slot')
        elif proof.source_kind == 'tool_result':
            records = [r for r in run.tool_results if r.seq == proof.source_index]
            calls = [i for i,c in enumerate(run.base.calls) if c.seq == proof.source_index]
            if len(records) != 1 or len(calls) != 1 or run.model_trace is None:
                raise ValueError('M04: tool disclosure has no unique recorded result/call')
            record = records[0]; index = calls[0]
            if (len(run.model_trace.call_requests) != len(run.base.calls)
                    or index >= response.available_results
                    or run.model_trace.call_requests[index] >= proof.request
                    or record.text_real != proof.source_text or record.text_masked != proof.masked_text
                    or record.spans_real.get(item.id) != (proof.source_start,proof.source_end)):
                raise ValueError('M04: tool disclosure is not proved available or slot-exact')
            # Reconstruct the MASKED offset from actual recorded replacements,
            # not a search for a similar-looking token elsewhere in the result.
            drift = 0; exact = False
            for start,end,fake,piece_type in sorted(record.pieces):
                if (start,end) == (proof.source_start,proof.source_end):
                    if piece_type != item.type:
                        raise ValueError('M04: replaced piece type does not match declared item type')
                    exact = ((start+drift,start+drift+len(fake)) == (proof.masked_start,proof.masked_end)
                             and fake == proof.masked_text[proof.masked_start:proof.masked_end])
                drift += len(fake)-(end-start)
            if not exact:
                raise ValueError('M04: tool replaced piece is not an exact disclosure slot')
            literal=proof.source_text[proof.source_start:proof.source_end]
            if literal != item.value and not _equal(item.type,literal,item.canonical or item.value):
                raise ValueError('M04: tool source does not identify declared value version')
        else:
            raise ValueError('M04: unknown disclosure source kind')
        if proof.source_kind == 'message' and proof.source_text[proof.source_start:proof.source_end] != item.value:
            raise ValueError('M04: literal source differs from declared source value')


@dataclass(frozen=True)
class Mapping:
    item_id: str
    identity: str
    pii_type: str
    role: str
    fake: str
    real: str
    availability: str              # available / unknown
    evidence: str
    literal: str | None

    @property
    def available(self) -> bool:
        return self.availability == 'available'

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.identity, self.pii_type, self.role, fold(self.real))


@dataclass(frozen=True)
class AnswerRestoreEvent:
    case_id: str
    repeat: int
    event_id: str
    raw_start: int
    raw_end: int
    delivered_start: int
    delivered_end: int
    written: str
    delivered: str
    expected: str
    item_ids: tuple[str, ...]
    pii_type: str
    role: str
    status: str
    evidence: str
    measurable: bool
    value_ok: bool
    form_ok: bool
    form_measured: bool
    residual: bool
    joint_ok: bool
    form_differs: tuple[str, ...]


@dataclass(frozen=True)
class AnswerRestoreRun:
    case_id: str
    repeat: int
    events: tuple[AnswerRestoreEvent, ...]
    text_status: str                 # preserved / changed / unresolved
    unmapped_changes: int
    raw_empty: bool


@dataclass(frozen=True)
class AnswerRestoreLine:
    pii_type: str
    candidates: int
    measurable: int
    unresolved: int
    value_ok: int
    form_ok: int
    form_unmeasured: int
    residual: int
    joint_ok: int
    statuses: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class AnswerRestoreAggregate:
    estimator: str
    runs: int
    answers_with_substitutes: int
    answers_without_substitutes: int
    answer_restore_clean: int
    answer_text_preserved: int
    answer_text_changed: int
    answer_text_unresolved: int
    unmapped_changes: int
    overall: AnswerRestoreLine
    by_type: tuple[AnswerRestoreLine, ...]


def _response_regions(run: ArmRunV5) -> tuple[tuple[int, int, object], ...]:
    """Exact whole-response or final-turn concatenation, never last-row guessing."""
    if run.model_trace is None:
        return ()
    responses = run.model_trace.responses
    nonempty_turns = {r.turn for r in responses if r.raw}
    # The final answer is the LAST nonempty turn. An earlier coincidentally
    # matching response cannot rescue inconsistent final-answer provenance.
    for turn in ([max(nonempty_turns)] if nonempty_turns else []):
        rows = [r for r in responses if r.turn == turn and r.raw]
        if '\n'.join(r.raw for r in rows) != run.reply_raw:
            continue
        out = []; cursor = 0
        for r in rows:
            out.append((cursor, cursor + len(r.raw), r)); cursor += len(r.raw) + 1
        return tuple(out)
    return ()


def _mapping_rows(case: CaseV5, run: ArmRunV5, response: object | None,
                  evidence: AnswerEvidence | None = None) -> tuple[Mapping, ...]:
    items = {p.id: p for p in case.base.pii}
    hints = {(m.item_id,m.substitute) for m in run.mentions if m.substitute}
    hints.update((i,m[0]) for i,m in run.base.substitutes.items() if m[0])
    proofs = () if evidence is None else evidence.disclosures
    hints.update((p.item_id,p.masked_text[p.masked_start:p.masked_end]) for p in proofs)
    rows=[]
    for item_id,fake in sorted(hints):
        item=items.get(item_id)
        if item is None:
            continue
        real=item.canonical or item.value
        if _equal(item.type,fake,real):
            continue
        matching=[p for p in proofs if p.item_id==item_id and
                  p.masked_text[p.masked_start:p.masked_end]==fake]
        available=[p for p in matching if response is not None and p.request <= response.request]
        if available:
            for p in available:
                rows.append(Mapping(item.id,item.identity,item.type,'',fake,real,'available',
                    f'{p.record_id}:provider_input={p.request}',p.source_text[p.source_start:p.source_end]))
        else:
            # A later (future) disclosure cannot prove this spelling was NOT
            # already known through an unrecorded channel, so it stays an
            # unknown competitor rather than being silently dropped.
            rows.append(Mapping(item.id,item.identity,item.type,'',fake,real,'unknown',
                                'recorded_spelling_without_proved_consumer_disclosure',None))
        # Derived parts nominate occurrences but do NOT inherit an invented
        # literal correspondence from canonical parts or engine annotations.
        if item.type=='NAME':
            for role,f in parts_of('NAME',fake).items():
                r=item.parts.get(role,'')
                if r and f!=fake and not _name_equal(f,r):
                    rows.append(Mapping(item.id,item.identity,item.type,role,f,r,'unknown',
                                        'derived_role_requires_exact_disclosure',None))
            if any(n.kind=='initials' for n in value_needles('NAME',fake)):
                # Initials of a proved whole-name disclosure are themselves
                # provable; without such a disclosure they stay unknown.
                initials_avail = 'available' if available else 'unknown'
                rows.append(Mapping(item.id,item.identity,item.type,'initials',fake,real,initials_avail,
                                    'derived_initials_from_whole_name_disclosure' if available
                                    else 'derived_initials_candidate_not_identity_proof',None))
    return tuple(dict.fromkeys(rows))


def _word_boundary(text: str, a: int, b: int) -> bool:
    return ((a == 0 or not (text[a-1].isalnum() or text[a-1] == '_')) and
            (b == len(text) or not (text[b].isalnum() or text[b] == '_')))


def _placed(mapping: Mapping, raw: str) -> tuple[tuple[int, int], ...]:
    hits=set()
    if mapping.role == 'initials':
        return tuple(sorted({hit for n in value_needles('NAME',mapping.fake) if n.kind=='initials'
                             for hit in _needle_spans(n,raw)}))
    if mapping.pii_type == 'NAME':
        words=list(WORD.finditer(raw)); width=len(WORD.findall(mapping.fake))
        if 1 <= width <= 4:
            for i in range(len(words)-width+1):
                a,b=words[i].start(),words[i+width-1].end()
                middle=raw[a:b]
                if all(not re.search(r'[^\s-]',raw[words[j].end():words[j+1].start()])
                       for j in range(i,i+width-1)) and _name_equal(middle,mapping.fake):
                    hits.add((a,b))
    else:
        for needle in value_needles(mapping.pii_type, mapping.fake):
            if needle.kind in ('stem','initials'):
                continue  # Candidates from approximate stems can't prove identity.
            for a,b in _needle_spans(needle,raw):
                # Do not include sentence punctuation in the value's grouping.
                while b>a and raw[b-1] in ' \t\r\n.,;:': b-=1
                while a<b and raw[a] in ' \t\r\n': a+=1
                if a<b and _word_boundary(raw,a,b) and _equal(mapping.pii_type,raw[a:b],mapping.fake):
                    hits.add((a,b))
    return tuple(sorted(hits))


def _spelling_matches(mapping: 'Mapping', raw_span: str, fake: str) -> bool:
    """Does a raw occurrence correspond to a mapping's fake spelling?

    For an initials role the occurrence is the squeezed initials of the fake, not
    the whole name; the whole-name `_equal` would never match «П.О.» to
    «Пахомова Ольга».
    """
    if mapping.role == 'initials':
        return _squeeze_initials(raw_span) in initials_of(mapping.pii_type, fake)
    return _equal(mapping.pii_type, raw_span, fake)


def _candidates(case: CaseV5, run: ArmRunV5,
                evidence: AnswerEvidence | None = None) -> list[tuple[int,int,tuple[Mapping,...]]]:
    regions=_response_regions(run)
    rows=_mapping_rows(case,run,None,evidence)
    all_hits={}
    qualified_cache = {None: rows}
    # Match raw FIRST; availability is asked of the response that wrote this span.
    for m in rows:
        for a,b in _placed(m,run.reply_raw):
            region=next((r for low,high,r in regions if low<=a and b<=high),None)
            cache_key = None if region is None else region.request
            if cache_key not in qualified_cache:
                qualified_cache[cache_key] = _mapping_rows(case, run, region, evidence)
            qualified=[x for x in qualified_cache[cache_key]
                       if x.key==m.key and _spelling_matches(m,run.reply_raw[a:b],x.fake)]
            all_hits.setdefault((a,b),[]).extend(qualified or [m])
    # Strong whole readings outrank their nested role hypotheses, not peers.
    intervals=sorted(all_hits,key=lambda x:(x[0],-(x[1]-x[0])))
    maximal=[iv for iv in intervals if not any(outer!=iv and outer[0]<=iv[0] and iv[1]<=outer[1]
                                               for outer in intervals)]
    out=[]
    for a,b in maximal:
        combined=list(all_hits[(a,b)])
        own_ids={m.item_id for m in combined}
        # A whole token suppresses its OWN redundant part hypotheses only.
        # Another owner nested inside it is retained as identity uncertainty.
        for (x,y), inner in all_hits.items():
            if (x,y)!=(a,b) and a<=x and y<=b:
                combined.extend(m for m in inner if m.item_id not in own_ids)
        maps=tuple(dict.fromkeys(combined))
        if out and a<out[-1][1]:
            p,q,old=out.pop(); out.append((p,max(q,b),tuple(dict.fromkeys(old+maps))))
        else: out.append((a,b,maps))
    return out


def _mapped_window(a: int,b: int,opcodes: Sequence[tuple], spans: Sequence[tuple[int,int]]) -> tuple[int,int,bool]:
    slices=[]; unresolved=False
    for tag,x,y,u,v in opcodes:
        if x==y:
            # Insertion in DELIVERED at raw position x. Only an insertion STRICTLY
            # inside the value span extends the value; one at the boundary is an
            # adjacent literal change and belongs to gap fidelity, not the value.
            if a < x < b:
                owners=sum(1 for s,e in spans if s<=x<=e)
                if owners==1: slices.append((u,v))
                else: unresolved=True
        elif x<b and a<y:
            if tag=='equal': slices.append((u+max(0,a-x),u+min(y-x,b-x)))
            else:
                if x<a or y>b: unresolved=True
                slices.append((u,v))
    if not slices: return 0,0,True
    return min(x for x,y in slices),max(y for x,y in slices),unresolved


def answer_events(case: CaseV5, run: ArmRunV5, *,
                  evidence: AnswerEvidence | None = None) -> AnswerRestoreRun:
    validate_evidence(case,run,evidence)
    raw,delivered=run.reply_raw,run.base.reply
    candidates=_candidates(case,run,evidence); spans=[(a,b) for a,b,_ in candidates]
    opcodes=SequenceMatcher(None,raw,delivered,autojunk=False).get_opcodes()
    events=[]
    for i,(a,b,maps) in enumerate(candidates):
        keys={m.key for m in maps}; available={m.key for m in maps if m.available}
        u,v,unknown=_mapped_window(a,b,opcodes,spans)
        available_maps=[m for m in maps if m.available]
        status=''; chosen=(available_maps or list(maps))[0]; text=delivered[u:v]
        literal_choices={m.literal for m in available_maps if m.fake==raw[a:b]}
        value=False; form=False; measured=False; residual=False; differs=()
        # A raw fake equal to somebody else's real value has ambiguous intent.
        collision=any(p.identity!=chosen.identity and
                      _equal(chosen.pii_type,raw[a:b],p.parts.get(chosen.role, '')
                             if chosen.role else (p.canonical or p.value))
                      for p in case.base.pii if p.type==chosen.pii_type)
        if len(keys)!=1 or collision or len(literal_choices)>1: status='ambiguous'
        elif available!=keys or any(m.availability=='unknown' for m in maps): status='provenance_unavailable'
        elif unknown: status='alignment_unresolved'
        else:
            if chosen.role == 'initials':
                # A derived initials form of a proved whole-name disclosure: the
                # value is the letter heads of the real name; residual means the
                # written fake initials survived unchanged.
                value = _initials_value_equal(text, chosen.real)
                residual = (_squeeze_initials(text) == _squeeze_initials(raw[a:b])) and not value
                if text.strip() and raw[a:b].strip():
                    form = text.count('.') == raw[a:b].count('.')
                    measured = True
                    differs = () if form else ('initials_separators',)
            else:
                # A literal copy is judged against the source at THAT disclosure,
                # not a repaired canonical or an unrelated alias's canonical. An
                # exact raw spelling with a single proved literal is the copy path;
                # anything else (renotation, non-literal fake) is the value path.
                exact_copy = len(literal_choices) == 1
                value = (text == next(iter(literal_choices))) if exact_copy else _equal(chosen.pii_type,text,chosen.real)
                residual=_equal(chosen.pii_type,text,raw[a:b]) and not value
                if chosen.pii_type in contracts.FORM_FEATURES and text.strip():
                    verdict=form_match(chosen.pii_type,text,raw[a:b])
                    form=verdict.same; measured=True; differs=tuple(sorted(verdict.differs))
            status=('residual' if residual else 'value_wrong' if not value else
                    'form_unmeasured' if not measured else 'form_wrong' if not form else 'matched')
        measurable=status not in ('ambiguous','provenance_unavailable','alignment_unresolved')
        expected_text = next(iter(literal_choices)) if len(literal_choices)==1 else chosen.real
        events.append(AnswerRestoreEvent(case.base.id,run.base.repeat,f'{a}:{b}:{i}',a,b,u,v,
            raw[a:b],text,expected_text,
            tuple(sorted({m.item_id for m in maps})),
            chosen.pii_type if len({m.pii_type for m in maps})==1 else '',chosen.role,status,
            ';'.join(sorted({m.evidence for m in maps})),measurable,value,form,measured,residual,
            measurable and value and form and not residual,differs))
    # Every change must be attributable to a MINIMAL raw token, not a broad diff.
    text_status='preserved'; outside=0
    for tag,x,y,u,v in opcodes:
        if tag=='equal': continue
        owners=[(a,b) for a,b in spans if (a<=x<=b if x==y else x<b and a<y)]
        if not owners:
            outside+=1; text_status='changed'
        elif not any(a<=x and y<=b for a,b in owners):
            if text_status!='changed': text_status='unresolved'
    if any(e.status=='alignment_unresolved' for e in events) and text_status!='changed':
        text_status='unresolved'
    return AnswerRestoreRun(case.base.id,run.base.repeat,tuple(events),text_status,outside,not raw.strip())


def _line(kind: str, events: Sequence[AnswerRestoreEvent]) -> AnswerRestoreLine:
    c=Counter(e.status for e in events)
    return AnswerRestoreLine(kind,len(events),sum(e.measurable for e in events),
        sum(not e.measurable for e in events),sum(e.value_ok for e in events),
        sum(e.form_ok for e in events),sum(not e.form_measured for e in events),
        sum(e.residual for e in events),sum(e.joint_ok for e in events),
        tuple((s,c[s]) for s in STATUSES))


def aggregate(runs: Sequence[AnswerRestoreRun]) -> AnswerRestoreAggregate:
    events=[e for r in runs for e in r.events]; types=sorted({e.pii_type for e in events})
    eligible=[r for r in runs if r.events]
    return AnswerRestoreAggregate(ESTIMATOR_VERSION,len(runs),len(eligible),len(runs)-len(eligible),
        sum(r.text_status=='preserved' and all(e.joint_ok for e in r.events) for r in eligible),
        sum(r.text_status=='preserved' for r in runs),sum(r.text_status=='changed' for r in runs),
        sum(r.text_status=='unresolved' for r in runs),sum(r.unmapped_changes for r in runs),
        _line('all',events),tuple(_line(t,[e for e in events if e.pii_type==t]) for t in types))


def render(result: AnswerRestoreAggregate) -> tuple[str,...]:
    pct=lambda x,n:f'{x}/{n} ({100*x/n:.2f}%)' if n else 'н/п (0/0)'
    out=[f'Actual answer restoration — {result.estimator}',
         'RAW written occurrences only; no required case hops. Delivered stream, not whole-text fallback.',
         'Unresolved candidates stay in headline; they are uncertainty, not proven engine failures.',
         f'answer_restore_clean: {pct(result.answer_restore_clean,result.answers_with_substitutes)}',
         f'answer_text_preserved: {pct(result.answer_text_preserved,result.runs)}; changed={result.answer_text_changed}; unresolved={result.answer_text_unresolved}',
         f'answers_without_substitutes: {result.answers_without_substitutes}/{result.runs} (no restoration score)',
         'type\tcandidates\tmeasurable\tunresolved\tvalue\tform\tresidual\tanswer_restore_joint\tjoint_measurable']
    for line in (result.overall,)+result.by_type:
        out.append('\t'.join([line.pii_type or 'untyped',str(line.candidates),str(line.measurable),str(line.unresolved),
                             pct(line.value_ok,line.candidates),pct(line.form_ok,line.candidates),
                             pct(line.residual,line.candidates),pct(line.joint_ok,line.candidates),
                             pct(line.joint_ok,line.measurable)]))
    return tuple(out)
