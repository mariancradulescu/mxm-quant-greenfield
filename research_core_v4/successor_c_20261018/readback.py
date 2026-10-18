"""Two-workflow, GET-only readback of an already executed economic result.

No scientific kernel, App credential, checkpoint writer or broker client.
The second workflow starts with a fresh GitHub token and encrypted handoff.
Confidential economics stay encrypted with the existing OWNER public key.
"""
import gzip
import json
import math
import os
from pathlib import Path
import re
import tempfile
import urllib.request
from .prepare import require, encoded, fingerprint
from research_core_v4.remediation_p0_p4_20261015.safety import sha, strict_json, unpack
from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly

REPO = 'mariancradulescu/mxm-quant-greenfield'
BRANCH = 'mxm-remediation-p0-p4-20261015-v1'
OWNER = 'a830c132521bd4348454653f713e04f6107484fe'
SOURCE = {'release_id':410874094, 'asset_id':634550785,
          'ciphertext_sha256':'8d90bc69ab5537f53ab917386ecaa30048b674451b6add28879ba2c6b0d10463',
          'head_sha':'b013c8c08f5406a111ee25a4ab425856f4e5bb02', 'run_id':38288144447}
SUMMARY_SHA = 'c68b65d15ae6187287736745dc55f85fee5b94f91be6baee4b04f4345f914e68'
DESIGN_SHA = '5f9da2487c84f9176291ecfc7518d3a0c62396eb9b26e6265f00d29fdd706837'
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'verification/c-readonly'
FP = '464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11'

def original_encoding(value):
    return encoded(value)+b'\n'

def owner_unchanged(route):
    require(route.json('git/ref/heads/mxm-o04-accepted-owner-1807-v1')['object']['sha']==OWNER,
            'C_OWNER_ROOT_CHANGED')

def workload(stage):
    require(os.environ.get('GITHUB_REPOSITORY')==REPO and
            os.environ.get('GITHUB_RUN_ATTEMPT')=='1', 'C_WORKLOAD')
    if stage=='fetch':
        require(os.environ.get('GITHUB_EVENT_NAME')=='push' and
                os.environ.get('GITHUB_REF_NAME')==BRANCH and
                os.environ.get('GITHUB_JOB')=='fetch-existing-result', 'C_FETCH_WORKLOAD')
    else:
        require(os.environ.get('GITHUB_EVENT_NAME')=='workflow_run' and
                os.environ.get('GITHUB_JOB')=='cold-economic-readback' and
                os.environ.get('C_SOURCE_SHA')==os.environ.get('C_EXPECTED_SOURCE_SHA') and
                re.fullmatch('[0-9a-f]{40}',os.environ.get('C_SOURCE_SHA','')), 'C_COLD_WORKLOAD')

def fetch(route):
    workload('fetch');owner_unchanged(route)
    run=route.json('actions/runs/'+str(SOURCE['run_id']))
    require(run['conclusion']=='success' and run['head_sha']==SOURCE['head_sha'] and
            run['run_attempt']==1, 'C_PRESERVED_RUN')
    from research_core_v4.remediation_p0_p4_20261015.control import lookup
    asset=lookup(route.json,SOURCE['release_id'],SOURCE['asset_id'],SOURCE['ciphertext_sha256'])
    require(asset['name']=='quotepath-private-result.mxmenc' and asset['size']<=16*1024*1024,
            'C_RESULT_ASSET')
    with route.open(asset['browser_download_url']) as response:
        blob=response.read(asset['size']+1)
    require(len(blob)==asset['size'] and sha(blob)==SOURCE['ciphertext_sha256'], 'C_CIPHER_BYTES')
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'preserved-result.mxmenc').write_bytes(blob)
    checkpoint={'schema':'mxm.c-readonly-handoff.v1','source':SOURCE,
                'source_sha':os.environ['GITHUB_SHA'],'fetch_run_id':int(os.environ['GITHUB_RUN_ID']),
                'owner_root':OWNER,'summary_sha256':SUMMARY_SHA,
                'purpose':'READ_EXISTING_RESULT_NO_SCIENTIFIC_REPLAY'}
    (OUT/'checkpoint.json').write_bytes(encoded(checkpoint))
    owner_unchanged(route)
    print(json.dumps({'state':'ENCRYPTED_RESULT_CHECKPOINT_READY','fetch_run_id':checkpoint['fetch_run_id'],
                      'scientific_recalculations':0,'broker_requests':0,'orders':0}))

def assess_summary(summary):
    """Interpret saved totals only. No source/feature/account recomputation."""
    require(summary['schema']=='mxm.quote.path.empirical.summary.v1' and
            summary['mechanism']=='PRICE_SPREAD_TEMPORAL_ORDER_RESPONSE_V1' and
            summary['design_sha256']==DESIGN_SHA, 'C_SUMMARY_IDENTITY')
    require(summary['broker_requests']==0 and summary['orders']==0 and summary['fills']==0 and
            summary['protected_forward'] is False and summary['alpha_certified'] is False and
            summary['HARD21_demonstrated'] is False, 'C_EXISTING_RESULT_SCOPE')
    p=summary['portfolio'];net=p['complete_net_eur'];selected=len(p['selected'])
    complete=(p['halt']=='END' and selected>0 and len(p['closed'])==selected and
              type(net) in (int,float) and math.isfinite(net))
    require(net is None or (type(net) in (int,float) and math.isfinite(net)), 'C_NONFINITE_RESULT')
    matched={}
    for name in ('midpoint','quote_count'):
        a=summary['accounting'][name];delta=a['paired_model_increment_eur']
        require(delta is None or (type(delta) in (int,float) and math.isfinite(delta)), 'C_NONFINITE_INCREMENT')
        matched[name]=delta if complete and a['paired_entries']==selected and a['unknown']==0 else None
    positive=complete and net>0 and all(v is not None and v>0 for v in matched.values())
    return {'schema':'mxm.c-existing-economic-assessment.v1',
            'existing_summary_sha256':sha(original_encoding(summary)),
            'complete_net_eur':net if complete else None,'complete_matched_increment_eur':matched,
            'decision':('EXPLORATORY_POSITIVE_REQUIRES_UNEXPOSED_CONFIRMATION' if positive else
                        'NO_ADVANCEMENT_INCOMPLETE_SUPPORT' if not complete or any(v is None for v in matched.values()) else
                        'NO_ADVANCEMENT_NONPOSITIVE_NET_OR_INCREMENT'),
            'temporal_halves_as_originally_saved':summary['temporal_halves'],
            'weekly_as_originally_saved':summary['weekly'],
            'cost_terms':summary['cost_terms'],'uncertainty':summary['uncertainty'],
            'scientific_recalculations':0,'new_experiment':False,
            'campaign_armed':False,'orders_allowed':False,'alpha_certified':False,'HARD21_demonstrated':False}

def cold(route):
    workload('cold');owner_unchanged(route)
    checkpoint=strict_json((OUT/'checkpoint.json').read_bytes())
    require(checkpoint=={'schema':'mxm.c-readonly-handoff.v1','source':SOURCE,
             'source_sha':os.environ['C_SOURCE_SHA'],'fetch_run_id':int(os.environ['C_FETCH_RUN_ID']),
             'owner_root':OWNER,'summary_sha256':SUMMARY_SHA,
             'purpose':'READ_EXISTING_RESULT_NO_SCIENTIFIC_REPLAY'},'C_HANDOFF_BINDING')
    blob=(OUT/'preserved-result.mxmenc').read_bytes()
    require(sha(blob)==SOURCE['ciphertext_sha256'],'C_COLD_CIPHER_DRIFT')
    from research_core_v4.remediation_p0_p4_20261015.owner import bounded_decrypt
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
    with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as directory:
        tmp=Path(directory);key,fp=_private_key_from_secret(tmp);require(fp==FP,'C_OWNER_KEY')
        raw=unpack(bounded_decrypt(blob,key,tmp));value=strict_json(raw,max_elements=8000000)
        require(original_encoding(value)==raw,'C_ORIGINAL_CANONICAL_ENCODING')
        summary=value['summary']
        require(sha(original_encoding(summary))==SUMMARY_SHA,'C_ACCEPTED_SUMMARY_CHANGED')
        assessment=assess_summary(summary)
        private={'schema':'mxm.c-private-readback.v1','checkpoint':checkpoint,'assessment':assessment,
                 'original_summary':summary,'cold_run_id':int(os.environ['GITHUB_RUN_ID'])}
        result_raw=encoded(private)
        path=OUT/'economic-readback.mxmenc'
        public_key=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem'
        require(public_spki_sha256(public_key)==FP,'C_OUTPUT_RECIPIENT')
        encrypt_shard(gzip.compress(result_raw,mtime=0),public_key=public_key,output=path)
        require(unpack(bounded_decrypt(path.read_bytes(),key,tmp))==result_raw,'C_ENCRYPTED_RESULT_READBACK')
    owner_unchanged(route)
    from research_core_v4.numeric_development_v1.public_output_guard_v1 import SCHEMA,ROOT as PUB,validate_public_blob
    status={'schema':SCHEMA,'phase':'FINAL','status':'PASS','source_head':os.environ['C_SOURCE_SHA'],
            'run_id':int(os.environ['GITHUB_RUN_ID']),'failure_code':'NONE',
            'encrypted_artifact_name':path.name,'encrypted_artifact_sha256':sha(path.read_bytes()),
            'scientific_design_sha256':DESIGN_SHA}
    public=validate_public_blob(PUB+'SUCCESSOR_C_EXISTING_READBACK_V1.json',status)
    (OUT/'public-status.json').write_bytes(public)
    print(public.decode().strip())
    with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:
        f.write('Cold workflow read verified the preserved economic summary; no experiment repeated. Confidential assessment encrypted with the existing OWNER key. No writer, broker I/O or orders.\n')

if __name__=='__main__':
    import sys
    route=GetOnly();original=urllib.request.urlopen;urllib.request.urlopen=route.open
    try:
        {'fetch':fetch,'cold':cold}[sys.argv[1]](route)
    except Exception as error:
        code=str(error) if re.fullmatch(r'C_[A-Z0-9_]+',str(error)) else type(error).__name__
        print(json.dumps({'state':'C_READONLY_STOP','safe_code':code}));raise SystemExit(1) from None
    finally:
        urllib.request.urlopen=original
