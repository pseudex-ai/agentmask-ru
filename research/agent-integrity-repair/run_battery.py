"""Run script-based offline regression suites with immutable before/after logs.
No live provider requests. Each test owns its own temporary test state.
"""
import json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent/sys.argv[1]
OUT.mkdir(parents=True,exist_ok=False)
TESTS=['test_loop','test_product','vault_test','test_persona_defects','test_overmasking','test_localui','test_hard_cases','test_names_morphology','test_credentials','test_coverage_152fz','test_perf_masking','test_identity_invariant','test_phase4b','test_derived_forms','test_address_composition','test_collisions','test_schema']
results=[]
for name in TESTS:
 start=time.monotonic()
 with (OUT/(name+'.log')).open('w') as log:
  try:
   p=subprocess.run([sys.executable,name+'.py'],cwd=ROOT/'prototype',env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},stdout=log,stderr=subprocess.STDOUT,timeout=240)
   code=p.returncode
  except subprocess.TimeoutExpired:
   code=124;log.write('\nBATTERY: isolated test exceeded240sec\n')
 row={'test':name,'exit_code':code,'seconds':round(time.monotonic()-start,2)};results.append(row)
 (OUT/'RESULTS.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(row),flush=True)
print('Finished; baseline failures are recorded, never silently treated as pass.',flush=True)
sys.exit(int(any(r['exit_code']!=0 for r in results)))
