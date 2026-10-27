"""Receive/restore exact encrypted cost result, never decrypt or replay source."""
import argparse,base64,hashlib,io,json,zipfile
from pathlib import Path
from .durable_spot_observation import FOLDER as ORIGINAL,MANIFEST_SHA
ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'docs/economic-development/20261027/observed-cost-fx-40488994775'
HEAD='e923f37efc2df64b82bd15c26fb60ffe44b9b64f';RUN=40488994775
ZIP_SHA='d4ce88a1ce8389f01ecfced07d6e297ab4c94331269a0ff5307acea96ebd1d18'
MEMBERS={'receipt.json':(1659,'7f86d54f855b8216ef02f42abdec515f11308552ae2d57d49486038bf90cdc3b'),
 'cold.json':(552,'2475705c55346244827b921e5658f643e6bdb3014878eed6cce5ca3c205b74ab'),
 'ledger.mxmenc':(5744,'344f505c0cf23fddbf796b362c34d0efe93497424256859fee8eb2fb93445890')}
def need(ok,why):
    if not ok:raise ValueError('OBSERVED_COST_FX_RESULT_'+why)
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):
    need(p.is_file() and not p.is_symlink() and p.stat().st_size<=2000000,'BOUNDED_REGULAR_FILE');return p.read_bytes()
def originals(folder):
    folder=Path(folder);need(not folder.is_symlink(),'REGULAR_FOLDER')
    raw=base64.b64decode(read(folder/'artifact.zip.b64').strip(),validate=True)
    need(len(raw)==7389 and sha(raw)==ZIP_SHA,'ORIGINAL_NATIVE_ZIP')
    entries={}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        need(set(z.namelist())==set(MEMBERS) and len(z.namelist())==3,'EXACT_ORIGINAL_MEMBERS')
        for n,(size,digest) in MEMBERS.items():
            need(z.getinfo(n).file_size==size,'BOUNDED_ORIGINAL_MEMBER');b=z.read(n)
            need(sha(b)==digest,'ORIGINAL_MEMBER_SHA');entries[n]=b
    for n in ('receipt.json','cold.json'):need(read(folder/n)==entries[n],'EXACT_NATIVE_RECEIPT_COPY')
    return entries

def verify(folder=FOLDER):
    entries=originals(folder);r=json.loads(entries['receipt.json']);c=json.loads(entries['cold.json'])
    raw=read(ORIGINAL/'MANIFEST.json');need(sha(raw)==MANIFEST_SHA,'ORIGINAL_SOURCE_MANIFEST');m=json.loads(raw)
    need(r['schema']=='mxm.observed-cost-fx-native-reception.v1' and r['run_id']==RUN and r['source_sha']==HEAD and
      r['original_source_run']==40455704891 and r['original_source_head']==m['head'] and
      r['original_manifest_sha256']==MANIFEST_SHA and r['original_private_sha256']==m['private_sha256'],'ORIGINAL_NATIVE_PROVENANCE')
    need(r['policy_sha256']=='506b94740911f3a068dbe0b049c316b483ab8e4b1e7cd37fdcda9f9a8f68b4b0' and
      r['derived_input_sha256']=='c7b1b527db6f9ee4d16eff3c188a4f7230a98dd7db15b4ff42c3ac4f5e62c3b1' and
      r['csharp_assembly_sha256']=='e8df1483af6044bd8ea9e95af9afcc59de299b5d35898934fdc0d76630777a42','ORIGINAL_POLICY_INPUT_BINARY')
    counts={'1':{'ESTIMATE':330,'SOURCE_TICKET_BOOK_UNOBSERVED_INVALID_OR_TOO_OLD':6},
      '2':{'ESTIMATE':427,'FX_REQUIRED_BOOK_UNOBSERVED_INVALID_OR_TOO_OLD':52,'SOURCE_TICKET_BOOK_UNOBSERVED_INVALID_OR_TOO_OLD':3},
      '250':{'ESTIMATE':322}}
    need(r['events']==1140 and r['counts']==counts,'ALL_EVENT_CONDITIONAL_COMPONENT_COUNTS')
    for k in ('every_event_independently_reconciled','original_quality_profile_unchanged','original_diagnostic_exclusion_unchanged'):need(r[k] is True,'VERIFIED_'+k)
    for k in ('all_in_costs_proven','executable_fx_or_actual_charges_proven','full_entry_admission','hard21_proven','economic_edge_proven','native_robot_operational_reception_proven','market_prices_or_cost_values_public','source_timestamp_certified','stop_risk_proven','cloud_activated'):need(r[k] is False,'NO_PROMOTION_'+k)
    for k in ('new_broker_requests','orders','economic_model_runs','response_tests'):need(type(r[k]) is int and r[k]==0,'NO_SIDE_EFFECT_'+k)
    need(c['schema']=='mxm.observed-cost-fx-native-cold.v1' and c['run_id']==RUN and c['source_sha']==HEAD and c['events']==1140 and
      c['separate_custody_process_readback_verified'] is True and c['independent_algorithm_is_csharp_python_not_this_readback'] is True,'SEPARATE_NATIVE_CUSTODY_READBACK')
    need(r['encrypted_ledger_sha256']==c['encrypted_ledger_sha256']==MEMBERS['ledger.mxmenc'][1] and
      r['private_ledger_sha256']==c['private_ledger_sha256']=='5937c6e69ac98b292b8aed7e5f04b24c5b53227f797c755e56c743006b6dc1f5','ENCRYPTED_PRIVATE_LEDGER_IDENTITY')
    need(c['new_broker_requests']==c['orders']==0 and c['economic_edge_proven'] is False and c['native_robot_operational_reception_proven'] is False,'COLD_NO_PROMOTION')
    return dict(schema='mxm.immutable-observed-cost-fx-verification.v1',run_id=RUN,source_sha=HEAD,events=1140,
      conditional_component_estimates=1079,unresolved=61,original_quality_profile_unchanged=True,source_or_ledger_decrypted=False,
      new_broker_requests=0,orders=0,economic_edge_proven=False,native_robot_operational_reception_proven=False)

def restore_cipher(out,folder=FOLDER):
    result=verify(folder);out=Path(out)
    need(not any(p.is_symlink() for p in (out,*out.parents)) and not out.exists(),'NEW_REGULAR_OUTPUT_DIRECTORY')
    cipher=originals(folder)['ledger.mxmenc'];out.mkdir(parents=True,exist_ok=False)
    with (out/'ledger.mxmenc').open('xb') as f:f.write(cipher)
    return {**result,'encrypted_ledger_restored':True}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out');args=p.parse_args()
    print('MXM_VERIFIED_ORIGINAL_OBSERVED_COST_FX '+json.dumps(restore_cipher(args.out) if args.out else verify(),sort_keys=True))
