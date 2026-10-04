"""Independent probes for the four reported foundation defects.

Read-only against the frozen two M1a files. Results are written by the caller
to foundation-review-2; this module only computes.
"""
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'prototype'))
from bench.agentpii5.answer_restoration import (  # noqa: E402
    AnswerEvidence, DisclosureProof, answer_events, aggregate)
from bench.agentpii5.contracts import (MentionRecord, ModelResponse,  # noqa: E402
                                       ModelTrace, ToolResultRecord)
from bench.agentpii5.fixtures import (_call, _case, _in_message, _item, _run,  # noqa: E402
                                      _with_calls, _with_replies, _with_subs)

REAL = '+79164021187'
FAKE = '+79990001122'


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def base_fixture(kind='PHONE', real=REAL, fake=FAKE, canonical=None, identity='person1'):
    item = _item('p1', kind, real, canonical or real, identity, _in_message(0, 0, len(real)))
    case = _case('probe', 'single', (real,), (item,), ())
    run = _with_replies(_with_subs(_run('probe'), {'p1': fake}), fake, real, '')
    run = replace(run, mentions=(MentionRecord('p1', 0, -1, fake, 1),), request_count=1,
                  model_trace=ModelTrace((ModelResponse(1, 0, 0, fake, real),), ()))
    proof = DisclosureProof('probe-message', 1, 'p1', 'message', 0, real, fake,
                            0, len(real), 0, len(fake), sha(real), sha(fake))
    return case, run, AnswerEvidence((proof,))


def homoglyph_fixture():
    # source contains Cyrillic О; canonical is the repaired Latin/digit form.
    source = '8(916)4\u041e2-11-87'   # Cyrillic О
    canonical = '8(916)402-11-87'
    fake = '8(999)000-11-22'
    item = _item('p1', 'PHONE', source, canonical, 'person1', _in_message(0, 0, len(source)))
    case = _case('probe', 'single', (source,), (item,), ())
    run = _with_replies(_with_subs(_run('probe'), {'p1': fake}), fake, canonical, '')
    run = replace(run, mentions=(MentionRecord('p1', 0, -1, fake, 1),), request_count=1,
                  model_trace=ModelTrace((ModelResponse(1, 0, 0, fake, canonical),), ()))
    proof = DisclosureProof('probe-homoglyph', 1, 'p1', 'message', 0, source, fake,
                            0, len(source), 0, len(fake), sha(source), sha(fake))
    return case, run, AnswerEvidence((proof,))


def two_proof_alias_fixture(delivered):
    # Same identity, two explicit proofs: canonical message fake and bare
    # 11-digit tool fake. raw is the bare fake, delivered is a renotation.
    bare_real = '89164021187'
    bare_fake = '89990001122'
    case, run, ev = base_fixture()
    run = _with_calls(run, (_call('crm_find_contact', {}, {}, {}, '', 0),), (0,))
    record = ToolResultRecord('crm_find_contact', 0, 0, 0, 'text', bare_real, bare_fake,
                              {'p1': (0, len(bare_real))},
                              ((0, len(bare_real), bare_fake, 'PHONE'),), False)
    run = replace(run, tool_results=(record,),
                  model_trace=ModelTrace((ModelResponse(1, 0, 0, '', ''), ModelResponse(2, 0, 1, bare_fake, delivered)), (1,)),
                  base=replace(run.base, reply=delivered), reply_raw=bare_fake)
    tool = DisclosureProof('probe-tool', 2, 'p1', 'tool_result', 0, bare_real, bare_fake,
                           0, len(bare_real), 0, len(bare_fake), sha(bare_real), sha(bare_fake))
    return case, run, AnswerEvidence((ev.disclosures[0], tool))


def results():
    out = {}
    # Fix 1: silent homoglyph repair must NOT pass as a value; literal copy must.
    c, r, e = homoglyph_fixture()
    out['homoglyph_repaired_no_pass'] = aggregate((answer_events(c, r, evidence=e),)).overall.joint_ok == 0
    r_lit = replace(r, base=replace(r.base, reply='8(916)4\u041e2-11-87'))
    out['homoglyph_literal_pass'] = aggregate((answer_events(c, r_lit, evidence=e),)).overall.value_ok == 1
    # Fix 1 stronger: unrelated canonical alias must not license a bare-fake renotation.
    c, r, e = two_proof_alias_fixture('79164021187')   # renotation, not literal
    out['alias_repaired_no_pass'] = aggregate((answer_events(c, r, evidence=e),)).overall.joint_ok == 0
    c, r, e = two_proof_alias_fixture('89990001122')   # unchanged fake -> residual
    out['alias_unchanged_residual'] = aggregate((answer_events(c, r, evidence=e),)).overall.residual == 1

    # Fix 2: chronology validation rejects bool/float/missing ordinal/boundary.
    def rejected(c, r, e):
        try:
            answer_events(c, r, evidence=e)
        except ValueError:
            return True
        return False
    c, r, e = base_fixture()
    out['bool_call_request_rejected'] = rejected(
        c, replace(r, model_trace=ModelTrace((ModelResponse(1, 0, 0, FAKE, REAL),), (True,))), e)
    out['float_call_request_rejected'] = rejected(
        c, replace(r, model_trace=ModelTrace((ModelResponse(1, 0, 0, FAKE, REAL),), (0.5,))), e)
    out['float_available_rejected'] = rejected(
        c, replace(r, model_trace=ModelTrace((ModelResponse(1, 0, 0.5, FAKE, REAL),), ())), e)
    out['bool_available_rejected'] = rejected(
        c, replace(r, model_trace=ModelTrace((ModelResponse(1, 0, True, FAKE, REAL),), ())), e)
    out['unknown_request_rejected'] = rejected(
        c, replace(r, model_trace=ModelTrace((ModelResponse(1, 0, 0, FAKE, REAL),), (9,))), e)
    # Fix 2 with a real call so call_requests maps to a valid existing request.
    c2, r2, e2 = base_fixture()
    r2 = _with_calls(r2, (_call('crm_find_contact', {}, {}, {}, '', 0),), (0,))
    r2 = replace(r2, model_trace=ModelTrace((ModelResponse(1, 0, 0, '', ''), ModelResponse(2, 0, 1, FAKE, REAL)), (2,)))
    out['valid_tool_call_request_ok'] = not rejected(c2, r2, e2)

    # Fix 3: unknown piece engine_type must be refused.
    c3, r3, e3 = base_fixture()
    bare_real, bare_fake = '89164021187', '89990001122'
    r3 = _with_calls(r3, (_call('crm_find_contact', {}, {}, {}, '', 0),), (0,))
    record = ToolResultRecord('crm_find_contact', 0, 0, 0, 'text', bare_real, bare_fake,
                              {'p1': (0, len(bare_real))},
                              ((0, len(bare_real), bare_fake, 'NOT_A_TYPE'),), False)
    r3 = replace(r3, tool_results=(record,),
                 model_trace=ModelTrace((ModelResponse(1, 0, 0, '', ''), ModelResponse(2, 0, 1, bare_fake, REAL)), (1,)))
    tool = DisclosureProof('probe-type', 2, 'p1', 'tool_result', 0, bare_real, bare_fake,
                           0, len(bare_real), 0, len(bare_fake), sha(bare_real), sha(bare_fake))
    out['unknown_piece_type_rejected'] = rejected(c3, r3, AnswerEvidence((tool,)))

    # Fix 4: future proof must not erase an unknown competitor on another identity.
    c4, r4, e4 = base_fixture()
    other = replace(c4.base.pii[0], id='p2', identity='person2')
    c4 = replace(c4, base=replace(c4.base, pii=c4.base.pii + (other,)))
    r4 = replace(r4, mentions=r4.mentions + (MentionRecord('p2', 0, -1, FAKE, 1),),
                 model_trace=ModelTrace((ModelResponse(1, 0, 0, FAKE, REAL), ModelResponse(2, 0, 0, '', '')), ()))
    future = DisclosureProof('probe-p2-future', 2, 'p2', 'message', 0, FAKE, FAKE, 0, len(FAKE), 0, len(FAKE), sha(FAKE), sha(FAKE))
    # message disclosure for p2 requires p2.where to be a message slot; build it cleanly
    p2 = _item('p2', 'PHONE', REAL, REAL, 'person2', _in_message(0, 0, len(REAL)))
    c4 = _case('probe', 'single', (REAL,), (c4.base.pii[0], p2), ())
    r4 = _with_replies(_with_subs(_run('probe'), {'p1': FAKE, 'p2': FAKE}), FAKE, REAL, '')
    r4 = replace(r4, mentions=(MentionRecord('p1', 0, -1, FAKE, 1), MentionRecord('p2', 0, -1, FAKE, 1)),
                 request_count=1,
                 model_trace=ModelTrace((ModelResponse(1, 0, 0, FAKE, REAL), ModelResponse(2, 0, 0, '', '')), ()))
    future2 = DisclosureProof('probe-p2-future2', 2, 'p2', 'message', 0, REAL, FAKE, 0, len(REAL), 0, len(FAKE), sha(REAL), sha(FAKE))
    p1proof = DisclosureProof('probe-p1-msg', 1, 'p1', 'message', 0, REAL, FAKE, 0, len(REAL), 0, len(FAKE), sha(REAL), sha(FAKE))
    agg = aggregate((answer_events(c4, r4, evidence=AnswerEvidence((p1proof, future2))),))
    out['future_does_not_erase_unknown_competitor'] = (agg.overall.joint_ok == 0
                                                       and agg.overall.candidates == 1
                                                       and agg.overall.unresolved >= 1)
    return out


if __name__ == '__main__':
    out = results()
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    print('ALL_PASS' if all(out.values()) else 'SOME_FAILED')
