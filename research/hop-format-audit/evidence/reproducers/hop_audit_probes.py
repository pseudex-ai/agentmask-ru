"""Isolated production-core diagnostic; no model calls or source edits."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0,'/Users/igor/Projects/Obscura-v5-codex/prototype')
import testkit
from pseudex.detect_all import Detector
from pseudex.redact import mask_text, unmask_arguments, unmask_text
from pseudex.vault import Vault

testkit.load_dev_bundle()
detector=Detector()
rows=[]
for text in ('телефон восемь девятьсот пятьдесят ноль шесть сорок ноль один семь',
             'телефон 8 (916) 214-88-03'):
 vault=Vault(':memory:','hop-audit').for_conversation('isolated-probe')
 spans=detector.detect(text)
 masked=mask_text(text,vault,spans)
 match=re.search(r'(?:\+7|8)[\d ()-]{9,}',masked)
 if match is None:raise RuntimeError(f'No phone substitute in {masked!r}')
 token=match.group().strip()
 digits=re.sub(r'\D','',token)
 written='+7'+digits[-10:]
 argument=json.loads(unmask_arguments(json.dumps({'phone':written}),vault))['phone']
 answer=unmask_text(written,vault)
 rows.append({'input':text,'masked':masked,'agent_written':written,'tool_received':argument,'answer_received':answer,'shown_forms':vault.shown_forms()})
Path('/private/tmp/hop-audit-evidence/core-probes.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(rows,ensure_ascii=False,indent=2))
