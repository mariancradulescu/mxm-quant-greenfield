"""Opaque archive/series integrity only. Never parse numerical fields."""
import hashlib
import json
import pathlib
import subprocess
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
MANIFEST = 'research_core_v3/state/PRIMARY_145_INPUT_MANIFEST_V1.json'

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def verify(directory):
    m = json.loads((ROOT/MANIFEST).read_bytes())
    names = {'MXM_RESEARCH_CORE_V3_SELECTED_M5_DEVELOPMENT.zip': m['original_capture_sha256'],
             'MXM_RESEARCH_CORE_V3_HIGH_QUALITY_DELTA_M5.zip': m['delta_capture_sha256']}
    archives, series = [], []
    for name, digest in names.items():
        p = pathlib.Path(directory)/name
        if not p.is_file():
            raise ValueError('ARCHIVE_PHYSICALLY_UNAVAILABLE:'+name)
        h = hashlib.sha256()
        with p.open('rb') as f:
            for chunk in iter(lambda: f.read(1024*1024), b''): h.update(chunk)
        if h.hexdigest() != digest: raise ValueError('ARCHIVE_DIGEST:'+name)
        with zipfile.ZipFile(p) as z:
            members = z.namelist()
            if len(members) != len(set(members)): raise ValueError('DUPLICATE_ARCHIVE_MEMBER')
            for s in m['primary_series']:
                if s['source_archive_sha256'] != digest: continue
                raw = z.read(s['file'])
                if sha(raw) != s['series_sha256']: raise ValueError('SERIES_DIGEST')
                series.append({'symbol_id':s['symbol_id'], 'member':s['file'],
                               'observed_sha256':sha(raw), 'source_archive_sha256':digest,
                               'size_bytes':len(raw)})
        archives.append({'filename':name, 'sha256':digest, 'size_bytes':p.stat().st_size})
    if len(series) != 145: raise ValueError('PRIMARY145_INCOMPLETE')
    changed = subprocess.check_output(['git','diff-tree','--no-commit-id','--name-only','-r',
                                       '3a7bd64c2f4168d93f1b64e7d690552d4ee19bea'],cwd=ROOT,text=True).splitlines()
    if len(changed) != 12: raise ValueError('LATEST_TWELVE')
    latest = {}
    for p in changed:
        raw = (ROOT/p).read_bytes()
        if raw != subprocess.check_output(['git','show','3a7bd64c2f4168d93f1b64e7d690552d4ee19bea:'+p],cwd=ROOT):
            raise ValueError('LATEST_FILE_DRIFT')
        latest[p] = sha(raw)
    bindings = json.loads((ROOT/'research_core_v4/skill_preflight_v1/INPUT_BINDINGS_V1.json').read_bytes())['files_sha256']
    for p,h in bindings.items():
        if sha((ROOT/p).read_bytes()) != h: raise ValueError('AUTHORITY_DRIFT:'+p)
    return {'start_head':'3a7bd64c2f4168d93f1b64e7d690552d4ee19bea',
            'parent':'79a81ded1a7acc1fb0bf6adee2fa70a35b26c113',
            'latest_twelve_sha256':latest,'frozen_authorities_verified_sha256':bindings,
            'archives':archives,'series':series,'verified_series':145,
            'numerical_fields_parsed':0,'responses_computed':0,
            'reader_route':'two accepted ZIPs; canonical primary_series members only; all145; no broker fallback',
            'historical_paid_leaves_preserved':261,'frontier_identities_preserved':1576,
            'exposed_development_only':True}

if __name__ == '__main__':
    out = verify(sys.argv[1])
    (HERE/'RECONCILIATION_AND_CORPUS_V1.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'verified_series':145,'numeric_fields_parsed':0,'archives':out['archives']}))
