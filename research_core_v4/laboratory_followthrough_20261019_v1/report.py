"""Reconcile original selected prefix after saved recovery; never replay pilot."""
import base64,gzip,hashlib,io,json,math,os,re,tempfile,urllib.request,zipfile,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE='docs/laboratory-completion/20261019/'
SOURCE='9e2ac4b4d8bba8c13f0df8e9407f1b3d9a6a9db9'
TRIGGER='a4b73df710bb97397c003d9de099972206720a56'
ZIP='d8533b8b23b24aa82cda6cd4bd40766475351be2dd08cd8fd676e88e7d4ad37b'
CIPHER='70af7c7acf00e44f835cbd128fad90e5d5596b6941c230d36ac472373272c82b'
DESIGN='4407d234693508ea4f941b8acd05bb8f25a3d9f6f3df5cb5e0d409f0d8ff4147'
ARMS=('model','midpoint','quote_count')

def need(v,c):
    if not v:raise ValueError('FOLLOW_'+c)
def sha(b):return hashlib.sha256(b).hexdigest()
def enc(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def reconcile(pilot,recovery):
    rows=pilot['selected_accounting'];selected={(r['sid'],r['t']):r for r in rows}
    need(len(selected)==len(rows),'DUPLICATE_SELECTED')
    patches={}
    for target in recovery['targets']:
        key=(target['symbol_id'],target['entry_second'])
        need(key in selected and target['scheduled_exit_second']==key[1]+900,'ORIGINAL_TARGET')
        for arm,value in target['recovered'].items():
            need(arm in ARMS and selected[key]['accounts'].get(arm) is None and (key,arm) not in patches,'REPLACEMENT_OR_DUPLICATE')
            need(type(value['net_eur']) in (int,float) and math.isfinite(value['net_eur']),'NONFINITE')
            patches[key,arm]=value
    merged=[]
    for row in rows:
        key=(row['sid'],row['t'])
        merged.append({a:patches.get((key,a),row['accounts'].get(a)) for a in ARMS})
    totals={}
    for arm in ARMS:
        known=[r[arm]['net_eur'] for r in merged if r[arm] is not None]
        totals[arm]={'selected_original_prefix':len(rows),'known':len(known),'missing':len(rows)-len(known),
                     'known_reference_net_subtotal_eur':sum(known) if known else None,
                     'complete_prefix_reference_net_eur':sum(known) if rows and len(known)==len(rows) else None}
    paired={}
    for arm in ARMS[1:]:
        pairs=[r['model']['net_eur']-r[arm]['net_eur'] for r in merged if r['model'] is not None and r[arm] is not None]
        paired[arm]={'known_pairs':len(pairs),'original_prefix_population':len(rows),
                     'known_paired_reference_increment_eur':sum(pairs) if pairs else None,
                     'complete_prefix_increment_eur':sum(pairs) if rows and len(pairs)==len(rows) else None}
    complete=bool(rows) and all(v['complete_prefix_reference_net_eur'] is not None for v in totals.values())
    positive=complete and totals['model']['complete_prefix_reference_net_eur']>0 and all(v['complete_prefix_increment_eur']>0 for v in paired.values())
    decision='DATA_INSUFFICIENT' if not complete else 'EXPLORATORY_REFERENCE_POSITIVE_NOT_CONFIRMED' if positive else 'NO_POSITIVE_COMPLETE_PREFIX_REFERENCE_NET_AND_INCREMENT'
    return {'schema':'mxm.original-selected-prefix-reconciliation.v1','classification':decision,'arms':totals,'paired':paired,
            'original_prefix_current_terms_identifiable':complete,'newly_recovered_arm_count':len(patches),
            'selection_extended_after_original_stop':False,'portfolio_replayed':False,
            'full_original_pilot_or_continuous_account_reconstructed':False,
            'reference_costs_are_saved_current_terms_and_scenarios':True,
            'historical_execution_certified':False,'confirmation_or_cbot_promotion':False}

def main():
    from research_core_v4.successor_c_20261018 import readback as old
    from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
    from research_core_v4.remediation_p0_p4_20261015 import owner
    from research_core_v4.remediation_p0_p4_20261015.safety import strict_json,unpack
    from research_core_v4.laboratory_completion_20261019_v2.runtime import read_binding,source_admission
    need(os.environ.get('GITHUB_REPOSITORY')==old.REPO and os.environ.get('GITHUB_EVENT_NAME')=='push' and
         os.environ.get('GITHUB_REF_NAME')==old.BRANCH and os.environ.get('GITHUB_JOB')=='saved-result-followthrough' and
         os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and not os.environ.get('SUCCESSOR_APP_PRIVATE_KEY'),'WORKLOAD')
    route=GetOnly();original=urllib.request.urlopen;urllib.request.urlopen=route.open
    try:
        source_admission(subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),os.environ['FOLLOW_SOURCE_SHA'],
            route.json('git/ref/heads/mxm-o04-successor-code-lab-followthrough-v1')['object']['sha'],route.json('rulesets/25222248'))
        old.owner_unchanged(route)
        need(route.json('git/ref/heads/mxm-o04-active-v1')['object']['sha']=='07d1ddbe0b83753bbf189770af1911623fef8d6f','AUTHORITY')
        run=route.json('actions/runs/39216105583');jobs=route.json('actions/runs/39216105583/jobs?per_page=100')['jobs']
        need(run['head_sha']==TRIGGER and run['conclusion']=='success' and run['run_attempt']==1 and
             {j['name'] for j in jobs}=={'recovery','frontier','admission'} and all(j['conclusion']=='success' for j in jobs),'PREVIOUS_NATIVE_CHAIN')
        blob=base64.b64decode((ROOT/BASE/'ADMISSION_39216105583.zip.b64').read_text().strip(),validate=True)
        need(sha(blob)==ZIP,'ARCHIVE')
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            need(set(z.namelist())=={'admission.mxmenc','admission-receipt.json'},'FILES')
            cipher=z.read('admission.mxmenc')
        need(sha(cipher)==CIPHER,'CIPHER')
        from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
        from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
        os.umask(0o077);out=ROOT/'verification/laboratory-followthrough';out.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as td:
            tmp=Path(td);key,fp=_private_key_from_secret(tmp);need(fp==old.FP,'OWNER_KEY')
            cp=strict_json(unpack(owner.bounded_decrypt(cipher,key,tmp)),max_elements=8000000)
            need(cp['stage']=='admission' and cp['source_sha']==SOURCE and cp['trigger_sha']==TRIGGER and cp['run_id']==39216105583 and
                 cp['design_sha256']==DESIGN and cp['pending'] is None,'CHECKPOINT_BINDING')
            values=cp['values'];admission=values['admission']
            need(admission['safe_stop'] is True and admission['cbot_qualified'] is False,'SAVED_ADMISSION')
            pilot=read_binding(route,old.SOURCE,key,tmp)
            need(sha(old.original_encoding(pilot['summary']))==old.SUMMARY_SHA,'PILOT_SUMMARY_PIN')
            result=reconcile(pilot,values['recovery'])
            private={'schema':'mxm.laboratory-followthrough-private.v1','input_admission_cipher_sha256':CIPHER,
                     'reconciliation':result,'original_recovery':values['recovery'],
                     'distinct_economic_study':values['frontier'],'saved_admission':admission}
            raw=enc(private);public=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem'
            need(public_spki_sha256(public)==old.FP,'RECIPIENT')
            dest=out/'followthrough.mxmenc';encrypt_shard(gzip.compress(raw,mtime=0),public_key=public,output=dest)
            need(unpack(owner.bounded_decrypt(dest.read_bytes(),key,tmp))==raw,'ENCRYPTED_READBACK')
        old.owner_unchanged(route)
        need(route.json('git/ref/heads/mxm-o04-active-v1')['object']['sha']=='07d1ddbe0b83753bbf189770af1911623fef8d6f','FINAL_AUTHORITY')
        allowed={'DATA_INSUFFICIENT','ORIGINAL_TARGETS_SUPPORTED_CURRENT_TERMS_ONLY','COST_UNRESOLVED','STRUCTURALLY_INFEASIBLE_ON_SAVED_REFERENCE_COHORT'}
        need(admission['original_exit_disposition'] in allowed and admission['distinct_study_disposition'] in allowed,'PUBLIC_ENUM')
        receipt={'schema':'mxm.laboratory-followthrough-public.v1','state':'SAVED_RESULT_INTERPRETED_AND_PREFIX_RECONCILED',
                 'run_id':int(os.environ['GITHUB_RUN_ID']),'source_sha':os.environ['FOLLOW_SOURCE_SHA'],
                 'original_exit_disposition':admission['original_exit_disposition'],
                 'distinct_study_disposition':admission['distinct_study_disposition'],
                 'original_prefix_reconciliation':result['classification'],
                 'original_prefix_current_terms_identifiable':result['original_prefix_current_terms_identifiable'],
                 'next_scientific_action':admission['next_scientific_action'],
                 'encrypted_sha256':sha(dest.read_bytes()),'app_key_used':False,'authority_writer':False,
                 'orders':0,'broker_requests':0,'pilot_replays':0,'v4_replays':0,'new_strategy_trials':0,
                 'cbot_qualified':False,'safe_stop':True,'numerical_economics_encrypted':True}
        (out/'public-verdict.json').write_bytes(enc(receipt));print(json.dumps(receipt,sort_keys=True))
    finally:urllib.request.urlopen=original

if __name__=='__main__':
    try:main()
    except Exception as error:
        code=str(error) if re.fullmatch(r'FOLLOW_[A-Z0-9_]+',str(error)) else type(error).__name__
        print(json.dumps({'state':'FOLLOWTHROUGH_SAFE_STOP','safe_code':code}));raise SystemExit(1) from None
