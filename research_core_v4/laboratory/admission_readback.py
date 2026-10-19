"""One finite read-only accounting bridge. Never migrates checkpoint16."""
import json,os,tempfile
from pathlib import Path
from . import frontier_pregate as b
from .admission import bootstrap_typed_book,TypedTrialBook
from .budgets import historical_accounting
from .common import need,digest,bytes_digest,encoded
from .custody import restore_ciphertext
from .runtime import file_at
from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
from research_core_v4.remediation_p0_p4_20261015 import owner
from research_core_v4.remediation_p0_p4_20261015.safety import strict_json,unpack

PARENT='0fc5128b686dca5ac8e08aa5dbe7fe9185ec62a7'
WF='.github/workflows/mxm-typed-admission-proof.yml'

def main():
    need(os.environ['GITHUB_JOB']=='readback' and os.environ['GITHUB_RUN_ATTEMPT']=='1' and os.environ['GITHUB_REPOSITORY']==b.old.REPO and os.environ['GITHUB_REF_NAME']==b.old.BRANCH,'ADMISSION_WORKLOAD')
    need(not any(os.environ.get(k) for k in ('SUCCESSOR_APP_PRIVATE_KEY','CTRADER_CLIENT_ID','CTRADER_CLIENT_SECRET','CTRADER_ACCESS_TOKEN')),'ADMISSION_READ_ONLY_CREDENTIALS')
    route=GetOnly();b.SOURCE_BRANCH='mxm-o04-successor-code-typed-admission-r1';b.anchors(route)
    need(route.json('git/ref/heads/mxm-o04-integrated-laboratory-evidence')['object']['sha']==PARENT,'ADMISSION_EVIDENCE_MOVED')
    runs=route.json('actions/runs?per_page=100')['workflow_runs'];own=[r for r in runs if r['path']==WF]
    need(len(own)==1 and own[0]['id']==int(os.environ['GITHUB_RUN_ID']),'ADMISSION_ONE_FINITE_INVOCATION')
    need(not any(r['id']!=int(os.environ['GITHUB_RUN_ID']) and r['status'] in ('queued','in_progress','waiting','pending') and r['path'] in (WF,'.github/workflows/mxm-integrated-laboratory.yml','.github/workflows/mxm-native-quote-reuse.yml') for r in runs),'ADMISSION_CONCURRENT_RESEARCH')
    original=file_at(route,'program-state.json',PARENT);state=strict_json(original)
    need(state['sequence']==16 and state['pending'] is None and state['safe_stop'] is True and state['ciphertext_sha256']=='eb031d18ee5b517ea1d4c3e6378cb276c4f3f46e2da810b86b8aabcc01a3ba8f','ADMISSION_CHECKPOINT_BINDING')
    manifest=strict_json(file_at(route,state['ciphertext_path'],PARENT));blob=restore_ciphertext(manifest,lambda p:file_at(route,p,PARENT))
    need(bytes_digest(blob)==state['ciphertext_sha256'],'ADMISSION_CIPHER')
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    os.umask(0o077)
    with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as td:
        tmp=Path(td);key,fp=_private_key_from_secret(tmp);need(fp==b.old.FP,'ADMISSION_OWNER_KEY')
        private=strict_json(unpack(owner.bounded_decrypt(blob,key,tmp)),max_elements=8000000);before=digest(private)
        need(private['sequence']==16 and private['pending'] is None and private['source_sha']==state['source_sha'],'ADMISSION_PRIVATE_BINDING')
        saved=private['programmes']['VOLUME_SURPRISE_CLOSE_LOCATION_PRESSURE_20261019_A']
        need(saved['progress']['safe_stop'] is True and 'screen_pressure' not in saved['progress']['results'],'ADMISSION_C033_NOT_REOPENED')
        candidates=[json.loads(p.read_bytes()) for p in sorted((b.ROOT/'discovery/candidates').glob('V2-C*.json'))]
        candidates.append(saved['progress']['results']['freeze_pressure']['value'])
        need(len(candidates)==33,'ADMISSION_CANDIDATE_HISTORY')
        history=historical_accounting(b.ROOT);book=bootstrap_typed_book(history,private['trial_book'],candidates)
        need(TypedTrialBook.restore(book.export()).export()==book.export() and digest(private)==before,'ADMISSION_READ_ONLY_ROUNDTRIP')
        need(book.view()['lanes']['V2']=={'limit':84,'outcome_charged':21,'reservation_holds':1,'encumbered':22} and book.view()['economic_observations']==29,'ADMISSION_NATIVE_COUNTERS')
        receipt={'schema':'mxm.typed-admission-readback-proof.v1','source_sha':os.environ['PREGATE_SOURCE_SHA'],'trigger_sha':os.environ['GITHUB_SHA'],'run_id':int(os.environ['GITHUB_RUN_ID']),
          'parent_evidence':PARENT,'original_state_sha256':bytes_digest(original),'input_cipher_sha256':bytes_digest(blob),'input_private_sha256':before,
          'typed_baseline_sha256':digest(book.export()),'view':book.view(),'historical_candidate_semantics_bound':33,
          'legacy_checkpoint_migrated':False,'legacy_bytes_unchanged':True,'new_programmes_registered':0,'new_reservations':0,'new_outcomes':0,'broker_requests':0,'orders':0,
          'confirmation_opened':False,'safe_stop':True,'economic_admission_released':False,'cbot_qualified':False}
    b.anchors(route);need(file_at(route,'program-state.json',PARENT)==original and route.json('git/ref/heads/mxm-o04-integrated-laboratory-evidence')['object']['sha']==PARENT,'ADMISSION_ORIGINAL_CHANGED')
    out=b.ROOT/'verification/typed-admission';out.mkdir(parents=True,exist_ok=True);(out/'receipt.json').write_bytes(encoded(receipt))
    print('MXM_TYPED_ADMISSION_PROOF '+json.dumps(receipt,sort_keys=True))

if __name__=='__main__':main()
