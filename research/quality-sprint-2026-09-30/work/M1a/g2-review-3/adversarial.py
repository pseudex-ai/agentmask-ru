"""Independent adversarial hunt for false-passes (g2-review-3)."""
import hashlib, json, sys
from dataclasses import replace
from pathlib import Path

ROOT=Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT/'prototype'))
from bench.agentpii5.answer_restoration import answer_events, aggregate, AnswerEvidence, DisclosureProof
from bench.agentpii5.contracts import MentionRecord, ModelResponse, ModelTrace
from bench.agentpii5.fixtures import _case,_item,_in_message,_run,_with_subs,_with_replies

REAL='+79164021187'; FAKE='+79990001122'
def sha(t): return hashlib.sha256(t.encode()).hexdigest()

def ev_of(kind, real, fake, raw, delivered, canonical=None):
    item=_item('p1',kind,real,canonical or real,'person1',_in_message(0,0,len(real)))
    case=_case('m04','single',(real,),(item,),())
    run=_with_replies(_with_subs(_run('m04'),{'p1':fake}),raw,delivered,'')
    run=replace(run,mentions=(MentionRecord('p1',0,-1,fake,1),),request_count=1,
                model_trace=ModelTrace((ModelResponse(1,0,0,raw,delivered),),()))
    proof=DisclosureProof('p',1,'p1','message',0,real,fake,0,len(real),0,len(fake),sha(real),sha(fake))
    e=answer_events(case,run,evidence=AnswerEvidence((proof,)))
    a=aggregate((e,))
    return e, a

def rec(name, e, a, note, expect_clean):
    """A false PASS = value/joint/clean overstates quality."""
    clean_ok = (a.answer_restore_clean == expect_clean)
    print(f"[{'PASS' if clean_ok else 'FAIL'}] {name}: value_ok={a.overall.value_ok} joint={a.overall.joint_ok} text={e.text_status} unmapped={e.unmapped_changes} clean={a.answer_restore_clean}", note)

def main():
    # 1. glued leading AND trailing insertion simultaneously.
    e,a=ev_of('PHONE',REAL,FAKE,'+79990001122','X+79164021187Y')
    rec('glued-both-sides', e, a, 'must not be clean', 0)

    # 2. duplicated real with a changed prefix.
    e,a=ev_of('PHONE',REAL,FAKE,'до +79990001122','до +79164021187 до +79164021187')
    rec('duplicated-real-changed-prefix', e, a, 'must not be clean', 0)

    # 3. value narrowed to a spurious inner occurrence (real substring appears twice).
    e,a=ev_of('PHONE',REAL,FAKE,'+79990001122','+79164021187+79164021187')
    rec('glued-duplicate-inner', e, a, 'must not be clean', 0)

    # 4. clean restore must stay preserved (no regression).
    e,a=ev_of('PHONE',REAL,FAKE,'+79990001122','+79164021187')
    rec('clean-restore', e, a, 'must be preserved/clean', 1)

    # 5. wrong-real-elsewhere must stay value_wrong + preserved.
    e,a=ev_of('PHONE',REAL,FAKE,'+79990001122; старый +79164021187','+79261234567; старый +79164021187')
    rec('wrong-real-elsewhere', e, a, 'must be value_wrong + preserved', 0)

    # 6. shared surrounding literals preserved.
    e,a=ev_of('PHONE',REAL,FAKE,'префикс +79990001122 хвост','префикс +79164021187 хвост')
    rec('shared-surrounding', e, a, 'must be preserved/clean', 1)

if __name__=='__main__':
    main()
