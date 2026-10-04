"""Offline regression suite and deterministic verifier-only package validation."""
import argparse,hashlib,json,subprocess,tempfile,zipfile
from pathlib import Path
from unittest.mock import patch
from tools import validate_v4_quote_probe_hardening as prior
from tools.build_v4_private_proof_package import build
RECORD='research_core_v4/state/QUOTE_SUPPORT_PRIVATE_PROOF_VERIFIER_PREPARATION_V1.json'
MODULES=prior.MODULES+['tests.test_v4_probe_return_intake','tests.test_v4_private_proof_verifier']
def sha(b):return hashlib.sha256(b).hexdigest()
def tests():
    with patch.object(prior,'MODULES',MODULES):return prior.offline_tests()
def package(root,archive,durable=False):
    root=Path(root);archive=Path(archive);record=json.loads((root/RECORD).read_bytes());raw=archive.read_bytes()
    with zipfile.ZipFile(archive) as z:
        names=z.namelist();prefix='MXM_V4_QUOTE_SUPPORT_PROBE_ANDROID_V1/'
        expected={prefix+n for n in ['V4_QUOTE_SUPPORT_PRIVATE_PROOF_RUN.py','V4_QUOTE_SUPPORT_PRIVATE_PROOF_VERIFY.py','PRIVATE_PROOF_AUTHORITY_V1.json','PRIVATE_PROOF_README.txt','PRIVATE_PROOF_PACKAGE_MANIFEST.json']}
        assert set(names)==expected and len(names)==5 and z.testzip() is None
        manifest=json.loads(z.read(prefix+'PRIVATE_PROOF_PACKAGE_MANIFEST.json'))
        assert manifest['existing_probe_files_overwritten'] is False
        assert set(manifest['file_sha256'])=={n.removeprefix(prefix) for n in expected if not n.endswith('PRIVATE_PROOF_PACKAGE_MANIFEST.json')}
        for n,h in manifest['file_sha256'].items():assert sha(z.read(prefix+n))==h
        for n in ['V4_QUOTE_SUPPORT_PRIVATE_PROOF_RUN.py','V4_QUOTE_SUPPORT_PRIVATE_PROOF_VERIFY.py']:assert z.read(prefix+n)==(root/n).read_bytes()
        a=json.loads(z.read(prefix+'PRIVATE_PROOF_AUTHORITY_V1.json'));intake=json.loads((root/'research_core_v4/state/QUOTE_SUPPORT_PROBE_RETURN_INTAKE_V1.json').read_bytes())
        assert a['compact_file_sha256']=={n:h for n,h in intake['input_zip']['file_sha256'].items() if n!='CHECKSUMS.sha256'}
        assert a['plan_sha256']=='e60b2dcb6cac33fd0f419daf0263d0003beaf1a0d77e7842a5ae690ff855bb16'
        assert not any(a[k] for k in ['network_authorized','broker_acquisition_authorized','raw_quote_export_authorized','scientific_response_authorized'])
    expected=record['android_verifier_package'];assert sha(raw)==expected['sha256'] and len(raw)==expected['size_bytes'] and len(names)==expected['members'] and archive.name==expected['filename']
    for n,h in record['source_file_sha256'].items():assert sha((root/n).read_bytes())==h
    for n,h in record['preserved_file_sha256'].items():assert sha((root/n).read_bytes())==h
    with tempfile.TemporaryDirectory() as d:
        rebuilt=Path(d)/archive.name;assert build(root,rebuilt)==expected and rebuilt.read_bytes()==raw
    state=json.loads((root/'research_core_v4/state/V4_STATE.json').read_bytes());assert state['status']=='QUOTE_SEQUENCE_BOUNDED_PROBE_COMPLETED_AWAITING_PRIVATE_OFFLINE_PROOF' and state['next_action']=='RUN_ZERO_NETWORK_PRIVATE_EVIDENCE_VERIFIER_ONLY'
    assert state['governance']['candidate_frozen_count']==0 and state['governance']['protected_forward_opened'] is False
    for path,h in record['historical_nested_state_sha256'].items():
        value=state
        for k in path.split('/'):value=value[k]
        assert sha(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())==h
    head=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD']).decode().strip()
    if durable:
        assert not subprocess.check_output(['git','-C',str(root),'status','--porcelain']).strip()
        assert subprocess.check_output(['git','-C',str(root),'show',head+':'+RECORD])==(root/RECORD).read_bytes()
        assert subprocess.check_output(['git','-C',str(root),'log','-1','--format=%H','--',RECORD]).decode().strip()==head
    return {'final_head':head,'package':expected,'deterministic':True,'internal_bindings_verified':True,'same_folder_overlay_only':True,'frozen_sources_preserved':True,'device_private_proof_still_pending':True,'broker_contacts':0,'historical_requests':0}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package',required=True);p.add_argument('--require-durable',action='store_true');v=p.parse_args();result=tests();result.update(package(Path(__file__).resolve().parents[1],v.package,v.require_durable));print(json.dumps(result,sort_keys=True))
