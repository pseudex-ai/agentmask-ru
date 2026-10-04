"""Preserve existing WIP and pin source/run inputs without altering originals.

No checkout, stash, fetch, commit, provider or engine execution. The archive is
private to the workspace and MUST NOT be added wholesale to public Git history.
Dependency wheels/cache are hashed/reference-pinned, not mistaken for authored WIP.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, io, json, os, platform, subprocess, sys, tarfile

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).parent
RUN=ROOT/'prototype/bench/runs/2026-09-30/v5-sprint-v2-813'

def git(*args):
    p=subprocess.run(['git',*args],cwd=ROOT,check=True,capture_output=True)
    return p.stdout

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def save(name,data):
    p=OUT/name
    if p.exists():raise FileExistsError(p)
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

archive=OUT/'private-wip-checkpoint.tar.gz'
if archive.exists():raise FileExistsError(archive)
tracked=[p for p in git('diff','--name-only','HEAD','-z').decode().split('\0') if p]
untracked=[p for p in git('ls-files','--others','--exclude-standard','-z').decode().split('\0') if p]
manifest=[]; referenced=[]; skipped=[]
with tarfile.open(archive,'w:gz') as tar:
    for name in sorted(set(tracked+untracked)):
        p=ROOT/name
        if p.is_relative_to(OUT):continue
        if p.is_symlink():
            skipped.append({'path':name,'reason':'symlink, target not followed','link':os.readlink(p)});continue
        if not p.is_file():
            skipped.append({'path':name,'reason':'deleted/nonregular, represented in git patch'});continue
        if p.name.startswith('.env') or any(x in ('secrets','.venv') for x in p.parts) or p.suffix in ('.key','.pem','.db'):
            skipped.append({'path':name,'reason':'credential/database path, not archived; remains untouched'});continue
        row={'path':name,'bytes':p.stat().st_size,'sha256':digest(p),'tracked':name in tracked}
        if any(x in ('dependencies','__pycache__','tmp') for x in p.relative_to(ROOT).parts):
            referenced.append(row);continue
        tar.add(p,arcname=name,recursive=False)
        manifest.append(row)
    for name,payload in (('CHECKPOINT-git-diff.patch',git('diff','--binary','HEAD')),
                         ('CHECKPOINT-git-status.txt',git('status','--short'))):
        info=tarfile.TarInfo(name);info.size=len(payload);tar.addfile(info,io.BytesIO(payload))
verified=0
with tarfile.open(archive,'r:gz') as tar:
    for row in manifest:
        handle=tar.extractfile(row['path']);h=hashlib.sha256()
        for block in iter(lambda:handle.read(1024*1024),b''):h.update(block)
        assert h.hexdigest()==row['sha256'],row['path']
        assert digest(ROOT/row['path'])==row['sha256'],('source changed during checkpoint',row['path'])
        verified+=1
save('WIP-MANIFEST.json',{'archive':str(archive.relative_to(ROOT)),'archive_sha256':digest(archive),
    'files':manifest,'verified_archive_and_source':verified,'reproducible_dependencies_referenced_only':referenced,
    'skipped_explicit':skipped,'not_a_git_commit':True,'not_for_publication':True})
# Independent prior planning baseline verifies no hidden product mutation.
prior=json.loads((ROOT/'research/quality-sprint-2026-09-30/BASELINE.json').read_text())
for row in prior['files']:assert digest(ROOT/row['path'])==row['sha256'],('prior baseline drift',row['path'])
old_manifest=json.loads((ROOT/'research/hop-format-audit/runs/cc3a551f-a8a5-4c0d-b90b-d3db2b26858a.manifest.json').read_text())
for row in old_manifest['files']:assert digest(RUN/row['path'])==row['sha256'],('paid raw drift',row['path'])
# Pin every tracked source/evaluator/lease file plus current authored new modules.
pinned=[]
for name in sorted(set(p for p in git('ls-files','-z').decode().split('\0') if p) | set(tracked+untracked)):
    p=ROOT/name
    if p.is_relative_to(OUT) or not p.is_file() or p.is_symlink():continue
    if name.startswith(('prototype/pseudex/','prototype/licensing/','prototype/bench/agentpii5/')) and p.suffix=='.py':
        pinned.append({'path':name,'sha256':digest(p),'bytes':p.stat().st_size})
for p in sorted(RUN.iterdir()):
    if p.is_file():pinned.append({'path':str(p.relative_to(ROOT)),'sha256':digest(p),'bytes':p.stat().st_size})
triples=[json.loads(s) for p in RUN.glob('*.triples.jsonl') for s in p.read_text().splitlines() if s]
statuses={s:sum(t['status']==s for t in triples) for s in sorted({t['status'] for t in triples})}
assert statuses=={'complete':802,'excluded':11},statuses
cases=json.loads((RUN/'corpus.v5.json').read_text())['corpus']
ladder_path=ROOT/'prototype/bench/agentpii5/ladder.json';ladder=json.loads(ladder_path.read_text())
intersection=sorted({c['base']['id'] for c in cases}&set(ladder['tiers']['holdout']))
assert not intersection,intersection
save('INPUTS.json',{'task':'B0','created_utc':datetime.now(timezone.utc).isoformat(),
    'root':str(ROOT),'head':git('rev-parse','HEAD').decode().strip(),
    'branch':git('branch','--show-current').decode().strip(),
    'v6_ref':git('rev-parse','origin/bench/agentpii6').decode().strip(),
    'sources':pinned,'source_manifest_sha256':hashlib.sha256(json.dumps(pinned,sort_keys=True).encode()).hexdigest(),
    'prior_88_hashes_verified':len(prior['files']),'paid_archive_hashes_verified':len(old_manifest['files']),
    'paid_run_statuses':statuses,'holdout_intersection':intersection,'ladder_file_sha256':digest(ladder_path),
    'holdout_claim_limit':'Only this run membership; historical holdout access is not proven absent.',
    'python':sys.version,'executable':sys.executable,'platform':platform.platform(),
    'production_digest':'NOT_VERIFIED; required before RG release comparison, not inferred from version.txt',
    'snapshot_scope':'authored dirty/untracked files and existing private evidence; dependency/cache files hash referenced',
    'worktree_clean':False,'authorization':'final-sprint-plan-approval + user goal launch; no paid benchmark/PR/merge/release/prod GO'})
(OUT/'pip-freeze.txt').write_bytes(subprocess.run([sys.executable,'-m','pip','freeze'],check=True,capture_output=True).stdout)
print(json.dumps({'wip_files_verified':verified,'dependencies_referenced':len(referenced),'skipped_explicit':skipped,
                  'archive_bytes':archive.stat().st_size,'pinned_source_run_files':len(pinned),
                  'previous_hashes':len(prior['files']),'paid_raw_files':len(old_manifest['files']),
                  'statuses':statuses,'holdout_intersection':len(intersection)},ensure_ascii=False,indent=2))
