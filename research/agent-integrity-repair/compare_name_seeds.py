"""Paired seeded script executions to distinguish NAME regressions from prior failures.
No source files are patched; randomness is controlled ONLY in isolated test processes.
"""
import json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent/'name-seed-comparison'
OUT.mkdir(exist_ok=True)
CODE='''import random,runpy,secrets,sys
source=sys.argv[1];rng=random.Random(int(sys.argv[2]));secrets.randbelow=rng.randrange;secrets.choice=rng.choice
sys.path.insert(0,source)
runpy.run_path(source+'/test_names_morphology.py',run_name='__main__')
'''
rows=[]
for seed in range(8):
 for label,source in [('before','/Users/igor/Projects/Obscura-v6-integration/prototype'),('after',str(ROOT/'prototype'))]:
  proc=subprocess.run([sys.executable,'-c',CODE,source,str(seed)],cwd=ROOT/'prototype',env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True)
  (OUT/f'{label}-{seed}.log').write_text(proc.stdout+'\nSTDERR\n'+proc.stderr)
  row={'seed':seed,'engine':label,'exit_code':proc.returncode,'failures':[line for line in proc.stdout.splitlines() if line.startswith('FAIL')]};rows.append(row)
  print(json.dumps(row,ensure_ascii=False),flush=True)
(OUT/'RESULTS.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
print('Completed: seeded comparison is diagnostic, not a reason to waive any existing failure.')
