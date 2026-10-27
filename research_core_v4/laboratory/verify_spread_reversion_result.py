"""Verify/restore exact native economic ciphertext and evaluator, no decryption/replay."""
import argparse,base64,hashlib,io,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'docs/economic-development/20261027/spread-reversion-40498420580'
MANIFEST_SHA='b0b022e283c00604a6512106bf6aa408a003adb05b301dc0a2d9bf58bd4b5396'
HEAD='414220cca9c0ecb2f7eb71910d1b199011f24520';RUN=40498420580
SPEC_SHA='169a1dce04bc7fa1fe3f0fc37aa7378566d08da9ec4d6817cc6d4d66df3e7eed'
def need(ok,why):
    if not ok:raise ValueError('SPREAD_ORIGINAL_RESULT_'+why)
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):
    need(p.is_file() and not p.is_symlink() and p.stat().st_size<=2000000,'BOUNDED_REGULAR_FILE');return p.read_bytes()
def originals(folder):
    folder=Path(folder);need(not folder.is_symlink(),'REGULAR_FOLDER');raw=read(folder/'MANIFEST.json')
    need(sha(raw)==MANIFEST_SHA,'IMMUTABLE_MANIFEST');m=json.loads(raw)
    need(m['run_id']==RUN and m['head']==HEAD and m['artifact_id']==12732241452 and len(m['parts'])==16,'ORIGINAL_ARTIFACT_IDENTITY')
    chunks=[]
    for i,part in enumerate(m['parts']):
        need(part['name']==f'part-{i:03d}.b64','ORDERED_ORIGINAL_PARTS');data=read(folder/part['name']).strip()
        need(len(data)==part['bytes'] and sha(data)==part['sha256'],'ORIGINAL_PART_BYTES');chunks.append(data)
    archive=base64.b64decode(b''.join(chunks),validate=True)
    need(len(archive)==m['zip_bytes']==566725 and sha(archive)==m['zip_sha256']=='347a96c63f3fb6faf6244f90b36be4d97d647f56d35dc33a85062ae95197b317','ORIGINAL_NATIVE_ZIP')
    entries={}
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        need(set(z.namelist())==set(m['members'])=={'receipt.json','cold.json','full-result.mxmenc','evaluator.dll'} and len(z.namelist())==4,'EXACT_ORIGINAL_MEMBERS')
        for name,v in m['members'].items():
            need(z.getinfo(name).file_size==v['bytes'] and v['bytes']<=2000000,'BOUNDED_MEMBER');data=z.read(name)
            need(sha(data)==v['sha256'],'ORIGINAL_MEMBER_BYTES');entries[name]=data
    for name in ('receipt.json','cold.json'):need(read(folder/name)==entries[name],'EXACT_NATIVE_RECEIPT_COPY')
    return m,entries

def verify(folder=FOLDER):
    m,e=originals(folder);r=json.loads(e['receipt.json']);c=json.loads(e['cold.json'])
    need(r['schema']=='mxm.spread-reversion-development-public.v1' and r['run_id']==RUN and r['source_sha']==HEAD and
      r['spec_sha256']==SPEC_SHA and r['source_run']==40179011821 and r['source_rows']==1275114 and r['source_groups']==812355,'EXACT_NATIVE_SOURCE_SPEC')
    need(sha((ROOT/'research_core_v4/laboratory/SPREAD_REVERSION_DEVELOPMENT_V1.json').read_bytes())==SPEC_SHA,'FROZEN_RESEARCH_IDENTITY')
    need(r['disposition']=='DATA_LIMITED' and r['gates']=={'all_complete_paths_observed':False,'all_five_days_gross_positive':False,'at_least_100_complete':True,'censor_at_most_5pct':False,'gross_spread_only_headroom_positive':False} and
      r['new_hypotheses']==r['model_trials']==1 and r['every_decision_episode_and_censor_reconciled'] is True and
      r['partition']=='DEVELOPMENT_ALREADY_EXPOSED' and r['next_action']=='STOP_FIXED_IDENTITY_NO_RETUNE_OR_AUTOMATIC_FOLLOWUP','ORIGINAL_VERDICT_BUDGET_AND_STOP')
    need(r['evaluator_sha256']==sha(e['evaluator.dll'])=='4bc0b433c5d25e512e4f045af505de938bf96c080eb220ffb770ce98cfebcfd1' and
      r['ciphertext_sha256']==sha(e['full-result.mxmenc'])=='bf8418b70e41d27ae86c72fc6ad36355427de50ba3bd5c0968ab70462bb79da4' and
      r['private_sha256']=='f25cf8416ff700e589d43f12cc101b94f2b56f31131eafa9db0ced2a3fc57423' and
      r['csharp_output_sha256']=='dbdfd54d98bad05a394ac86dcb8613f2b4e78f08c8acd8dc446eea2fdd2c4800','ORIGINAL_PRIVATE_OUTPUT_AND_BINARY')
    for k in ('capital_replay','cloud_activated','costs_defaulted_to_zero','formal_V2_or_C033_changed','hard21_proven','historical_costs_proven','native_robot_operational_reception_proven','net_edge_proven','protected_or_confirmation_opened'):need(r[k] is False,'NO_PROMOTION_'+k)
    for k in ('new_broker_requests','orders'):need(type(r[k]) is int and r[k]==0,'NO_SIDE_EFFECT_'+k)
    need(c['schema']=='mxm.spread-reversion-development-cold.v1' and c['run_id']==RUN and c['source_sha']==HEAD and c['spec_sha256']==SPEC_SHA and
      c['separate_custody_process_readback_verified'] is True and c['readback_is_not_independent_algorithm_or_confirmation'] is True,'SEPARATE_NATIVE_COLD_PROVENANCE')
    for k in ('ciphertext_sha256','private_sha256','evaluator_sha256'):need(c[k]==r[k],'COLD_ORIGINAL_'+k)
    need(c['net_edge_proven'] is False and c['new_broker_requests']==c['orders']==0,'COLD_NO_PROMOTION')
    return dict(schema='mxm.immutable-spread-reversion-verification.v1',run_id=RUN,head=HEAD,source_run=40179011821,source_rows=1275114,
      source_groups=812355,disposition='DATA_LIMITED',model_trials=1,original_evaluator_retained=True,source_or_result_decrypted=False,
      new_broker_requests=0,orders=0,net_edge_proven=False,hard21_proven=False,native_robot_operational_reception_proven=False)

def restore(out,folder=FOLDER):
    result=verify(folder);_,entries=originals(folder);out=Path(out)
    need(not any(p.is_symlink() for p in (out,*out.parents)) and not out.exists(),'NEW_REGULAR_OUTPUT_DIRECTORY');out.mkdir(parents=True,exist_ok=False)
    for name,data in entries.items():
        with (out/name).open('xb') as f:f.write(data)
    return {**result,'exact_encrypted_result_public_receipts_and_evaluator_restored':True}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out');a=p.parse_args()
    print('MXM_VERIFIED_ORIGINAL_SPREAD_REVERSION '+json.dumps(restore(a.out) if a.out else verify(),sort_keys=True))
