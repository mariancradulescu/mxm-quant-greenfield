"""Read-only, no-outcome reconciliation over preserved checkpoint16.
No broker credentials, candidate execution, return/PnL computation or booking.
Worker decrypts; separate keyless publisher appends evidence using existing custody.
"""
import gzip,json,os,re,subprocess,tempfile
from collections import Counter
from pathlib import Path
from .common import need,encoded,digest,bytes_digest,number
from .data import DataCatalogue
from .custody import restore_ciphertext,chunk_ciphertext,atomic_publish
from .runtime import file_at
from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
from research_core_v4.remediation_p0_p4_20261015 import owner
from research_core_v4.remediation_p0_p4_20261015.safety import strict_json,unpack
from research_core_v4.laboratory_completion_20261019_v2.runtime import source_admission
from research_core_v4.successor_c_20261018 import readback as old
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'verification/nonoutcome-reconciliation'
EVIDENCE='a54420b203cf0d662db472efa6660b9db7e7bbb1'
SOURCE_BRANCH='mxm-o04-successor-code-nonoutcome-reconciliation-r1'
ACTIVE='07d1ddbe0b83753bbf189770af1911623fef8d6f'
PROGRAMME='VOLUME_SURPRISE_CLOSE_LOCATION_PRESSURE_20261019_A'
PREFIX='diagnostics/reconciliation-20261019-r1'
DOC='fe92bee752e0ceebf4452014d6e5e2cf6791f2ae'
WF='.github/workflows/mxm-nonoutcome-reconciliation.yml'

def anchors(route):
    old.owner_unchanged(route)
    need(route.json('git/ref/heads/mxm-o04-active-v1')['object']['sha']==ACTIVE,'AUTHORITY_DRIFT')
    active=strict_json(file_at(route,'state.json',ACTIVE));need(active['revoked'] is False and active['pending'] is None,'AUTHORITY_REVOKED_OR_PENDING')
    source=os.environ['RECON_SOURCE_SHA']
    source_admission(subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),source,
      route.json('git/ref/heads/'+SOURCE_BRANCH)['object']['sha'],route.json('rulesets/25222248'))
    need(route.json('git/ref/heads/mxm-o04-successor-code-laboratory-r3')['object']['sha']=='f9bfc29c2cec87a87f9bd62bd5f38f1654c5b522','RECEPTION_SOURCE_DRIFT')
    need(route.json('git/ref/heads/mxm-o04-successor-code-laboratory-research-r4')['object']['sha']=='b430a303dc76bd1ea07fbd7dd9e91dcc7c7e9ee5','C033_SOURCE_DRIFT')

def budget_projection(history,private):
    book=private['trial_book'];item=book['identities']['V2:V2-C033']
    need(history['V2']['used']==21 and history['V2']['result_observations']==29,'HISTORICAL_ACCOUNTING')
    need(book['limits']['V2']==84 and book['used']['V2']==22 and item['units']==1 and item['state']=='RESERVED','C033_RESERVATION')
    return {'lane':'V2_ORIGINAL','frozen_limit':84,'contract_outcome_charged_identities':21,
      'economic_observations':29,'runtime_legacy_used_including_hold':22,
      'C033_existing_reservation_hold':1,'C033_new_economic_outcomes':0,
      'contract_not_yet_outcome_charged':63,'unencumbered_capacity_pending_policy':62,
      'refunds_or_counter_mutations':0,'legacy_prior_attempts':16,
      'global_universal_budget':None,'global_independent_effective_N':None,
      'categories':['INFORMATION_EXPOSURE','REGISTERED_IDENTITY','RESERVATION_HOLD','ECONOMIC_OUTCOME','PROGRAM_RESOURCE_BUDGET'],
      'new_economic_admissions':'BLOCKED_UNTIL_RECONCILIATION_AND_PROSPECTIVE_POLICY_COMPLETE'}

def diagnose_c033(saved,cache):
    definition=saved['programme'];draft=definition['tasks']['freeze_pressure']['input']['candidate']
    p=draft['parameters']['volume_pressure'];results=saved['progress']['results']
    need(saved['progress']['safe_stop'] is True and 'screen_pressure' not in results,'C033_CLOSED_NO_ECONOMICS')
    need(results['original_quotes']['classification']=='NO_ELIGIBLE_EVENTS','C033_VERDICT')
    need(results['causal_pressure']['value']['intents']==[],'C033_ZERO_SIGNAL_BINDING')
    public=[];details={}
    for name,sid in p['symbols'].items():
        ident=results['data_'+name]['value']['asset_id'];m=cache.assets[ident];rows=cache.rows[ident]
        need(m['instrument']==name and m['partition']=='DEVELOPMENT' and m.get('trust') in ('AUTHENTICATED_NATIVE_COLLECTION','AUTHENTICATED_NATIVE_CUSTODY'),'DIAGNOSTIC_AUTHENTIC_DATA')
        index={r['t']:r for r in rows};need(len(index)==len(rows),'DUPLICATE_DIAGNOSTIC_CLOCK')
        counts=Counter();ratios=[];locations=[];allvol=[r['volume'] for r in rows]
        need(all(number(v) and v>=0 for v in allvol),'INVALID_TICK_VOLUME')
        for decision in p['decision_times_ms']:
            obs=[index.get(decision-300000*j) for j in range(13,0,-1)]
            counts['scheduled']+=1
            if any(r is None for r in obs):counts['missing_clock']+=1;continue
            if any(r['available_at']>decision for r in obs):counts['late_available_at']+=1;continue
            if any(r['available_at']!=r['t']+300000 for r in obs):counts['availability_model_deviation']+=1
            counts['supported']+=1;bar=obs[-1];prior=obs[:-1];mean=sum(r['volume'] for r in prior)/12;span=bar['high']-bar['low']
            ratio=None
            if mean<=0:counts['prior_volume_zero']+=1
            else:
                counts['positive_prior_volume']+=1;ratio=bar['volume']/mean;ratios.append(ratio)
            volume_pass=ratio is not None and ratio>=2
            if volume_pass:counts['volume_condition']+=1
            if span<=0:counts['zero_range']+=1;continue
            location=(bar['close']-bar['low'])/span;locations.append(location)
            upper=location>=.8;lower=location<=.2;positive=bar['close']>bar['open'];negative=bar['close']<bar['open']
            counts['upper_close']+=int(upper);counts['lower_close']+=int(lower)
            counts['positive_body']+=int(positive);counts['negative_body']+=int(negative)
            counts['long_price_condition']+=int(upper and positive);counts['short_price_condition']+=int(lower and negative)
            counts['joint_long']+=int(volume_pass and upper and positive);counts['joint_short']+=int(volume_pass and lower and negative)
        nzero=sum(v==0 for v in allvol);constant=len(set(allvol))<=1
        cause='VOLUME_ALL_ZERO' if nzero==len(allvol) else 'VOLUME_CONSTANT' if constant else 'NO_VOLUME_SPIKES_AT_FROZEN_CLOCKS' if not counts['volume_condition'] else 'NO_JOINT_CONDITION_AT_FROZEN_CLOCKS'
        counts={k:int(counts[k]) for k in ('scheduled','supported','missing_clock','late_available_at','availability_model_deviation','prior_volume_zero','positive_prior_volume','volume_condition','zero_range','upper_close','lower_close','positive_body','negative_body','long_price_condition','short_price_condition','joint_long','joint_short')}
        public.append({'instrument':name,'symbol_id':sid,'rows':len(rows),'zero_volume_rows':nzero,'constant_volume':constant,'volume_unique_count':len(set(allvol)),'condition_counts':counts,'diagnostic_cause':cause,'normalized_rows_sha256':m['normalized_sha256']})
        def stats(vals):
            vals=sorted(vals)
            return None if not vals else {'minimum':vals[0],'q25':vals[(len(vals)-1)//4],'median':vals[(len(vals)-1)//2],'q75':vals[3*(len(vals)-1)//4],'maximum':vals[-1],'mean':sum(vals)/len(vals)}
        details[name]={'tick_volume':stats(allvol),'event_volume_ratio':stats(ratios),'close_location':stats(locations),'source_manifest':m}
    need(sum(r['condition_counts']['joint_long']+r['condition_counts']['joint_short'] for r in public)==0,'DIAGNOSTIC_CONTRADICTS_SEALED_ZERO')
    return {'symbols':public,'total_scheduled':sum(r['condition_counts']['scheduled'] for r in public),
      'total_supported':sum(r['condition_counts']['supported'] for r in public),
      'economic_outcomes_opened':0,'information_exposure':'NONOUTCOME_FEATURE_SUPPORT_AND_CONDITION_COUNTS_OPENED',
      'availability_semantics':'AVAILABLE_AT_EQUALS_BAR_CLOSE_IS_MODEL_NOT_ORIGINAL_RECEIPT_CERTIFICATE',
      'candidate_parameters_changed':False,'candidate_reopened':False},details

def inventory_and_frontier(route,corpus):
    from .inventory import inventory
    idx=inventory(ROOT)
    bindings=json.loads((ROOT/'research_core_v4/master_frontier_v1/SOURCE_AND_AUTHORITY_BINDINGS_V1.json').read_bytes())
    meta=json.loads((ROOT/'research_core_v4/master_frontier_v1/MACHINE_METADATA_RECONCILIATION_RESULT_V1.json').read_bytes())
    manifest=json.loads((ROOT/'data/DATA_MANIFEST.json').read_bytes())
    verified=[];changed=[]
    for b in bindings['bindings']:
        f=ROOT/b['path']
        if f.exists() and bytes_digest(f.read_bytes())==b['sha256']:verified.append(b['path'])
        else:changed.append(b['path'])
    # Exact membership carries prior structural/support data, never returns/rankings.
    members=meta['frontier_membership'];need(len(members)==1576 and len({m['symbol_id'] for m in members})==1576,'HISTORICAL_FRONTIER')
    classes=Counter(m['broker_native_context'] for m in members)
    primary=sum(m['historical_primary145'] for m in members)
    need(primary==145,'PRIMARY145_PROVENANCE')
    current={int(r['sid']):r for r in corpus['all_identity_status']}
    strata={}
    for cls in sorted(classes):
        cohort=[m for m in members if m['broker_native_context']==cls]
        strata[cls]={'historical_identities':len(cohort),'primary145_members':sum(m['historical_primary145'] for m in cohort),
          'historical_structural_support_limited':sum(m['accepted_structural_classification']=='SUPPORT_LIMITED_NOT_REJECTED' for m in cohort),
          'present_in_october_catalogue':sum(m['symbol_id'] in current for m in cohort),
          'entry_disabled_in_current_catalogue':sum('CURRENT_NOT_ENTRY_ENABLED' in current.get(m['symbol_id'],{}).get('reasons',[]) for m in cohort)}
    release=route.json('releases/tags/'+meta['accepted_corpus_release_tag'])
    assets={a['id']:a for a in release['assets']};available=[];unknown=[]
    for shard in meta['encrypted_shards_verified_by_release_metadata']:
        a=assets.get(shard['release_asset_id']);expected=shard['ENCRYPTED_ASSET_SHA256']
        good=a is not None and a['name']==shard['ENCRYPTED_ASSET_NAME'] and a['size']==shard['encrypted_bytes']
        if good and a.get('digest'):good=a['digest']=='sha256:'+expected
        record={'asset_id':shard['release_asset_id'],'name':shard['ENCRYPTED_ASSET_NAME'],'size':shard['encrypted_bytes'],'expected_sha256':expected,
          'metadata_match':good,'bytes_downloaded_in_this_reconciliation':False}
        (available if good else unknown).append(record)
    cps=corpus['summary']['checkpoints']
    native_refs=[{'phase':x.get('phase'),'release_id':x.get('release_id'),'asset_id':x.get('id',x.get('asset_id')),'ciphertext_sha256':x.get('ciphertext_sha256')} for x in cps]
    datasets=[{k:v for k,v in d.items() if k in ('dataset_id','state','resolution','interval','source_manifest','pack_sha256','sha256','classification')} for d in manifest['datasets']]
    evidence={'tracked_inventory':idx,'data_manifest_projection':datasets,'original_native_checkpoint_refs':native_refs,
      'shallow_release_metadata':available+unknown,'source_bindings_verified':verified,'source_bindings_changed_or_missing':changed,
      'frontier_membership':members}
    public={'historical_frontier_identities':1576,'historical_primary_nucleus':145,'frontier_is_permanent_cap':False,
      'primary145_is_exposed_development':True,'catalogue_access_is_preserved_october_reference_not_new_live_broker_check':True,
      'strata':strata,'source_bindings_verified':len(verified),'source_bindings_changed_or_missing':len(changed),
      'tracked_custody_inventory_entries':len(idx['tracked_assets']),'data_manifest_datasets':len(datasets),
      'original_native_checkpoints':len(native_refs),'original_checkpoint_phase_counts':dict(Counter(str(x.get('phase')) for x in cps)),
      'shallow_cipher_assets_metadata_matched':len(available),'shallow_cipher_assets_metadata_unresolved':len(unknown),
      'all_shallow_bytes_redownloaded_or_decrypted':False,
      'historical_stored_row_counts_recomputed':False,
      'broker_terms':'CURRENT_REFERENCE_NOT_HISTORICAL_COST_OR_MARGIN_AUTHORITY',
      'coverage_dimensions':{'classes':'STRATIFIED_FROM_BOUND_MEMBERSHIP','instruments':'EXACT_BOUND_IDENTITIES','resolution':'M5_SHALLOW_PLUS_PRIMARY_DEPTH_MANIFESTS_AND_TYPED_OTHER_DATASETS','sessions':'EXACT_CALENDARS_REQUIRED_NOT_INFERRED_FROM_GAPS','liquidity':'NATIVE_QUOTE_AGE_AND_SPREAD_SUPPORT_NOT_ALL_FILLS','costs':'DATED_AUTHORITY_REQUIRED_OR_VALID_FROZEN_BOUND','EUR200_margin':'CURRENT_ACCESS_REFERENCE_SEPARATE_FROM_HISTORICAL_REALIZATION'},
      'acquisition_allowed_now':False}
    return public,evidence

def worker():
    need(os.environ['GITHUB_JOB']=='reconcile' and os.environ['GITHUB_RUN_ATTEMPT']=='1' and os.environ['GITHUB_REPOSITORY']==old.REPO and os.environ['GITHUB_REF_NAME']==old.BRANCH,'RECON_WORKLOAD')
    need(not os.environ.get('SUCCESSOR_APP_PRIVATE_KEY') and not any(os.environ.get(k) for k in ('CTRADER_CLIENT_ID','CTRADER_ACCESS_TOKEN','CTRADER_CLIENT_SECRET')),'NO_BROKER_OR_APP_CREDENTIALS')
    route=GetOnly();anchors(route)
    need(route.json('git/ref/heads/mxm-o04-integrated-laboratory-evidence')['object']['sha']==EVIDENCE,'RECON_STALE_PARENT')
    runs=route.json('actions/runs?per_page=100')['workflow_runs']
    same=[r for r in runs if r['path']==WF and r['head_sha']==os.environ['GITHUB_SHA']]
    need(len(same)==1 and same[0]['id']==int(os.environ['GITHUB_RUN_ID']),'DUPLICATE_RECON_INVOCATION')
    state=strict_json(file_at(route,'program-state.json',EVIDENCE))
    need(state['sequence']==16 and state['pending'] is None and state['safe_stop'] is True,'C033_NOT_TERMINAL')
    jobs=route.json('actions/runs/39251815293/jobs?per_page=100')['jobs']
    need(all(any(j['name']==n and j['conclusion']=='success' for j in jobs) for n in ('investigation','durable-archive')),'C033_NATIVE_COMPLETION')
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
    from research_core_v4.autonomous_laboratory_20261019_v6.runtime import corpus,registry
    from .budgets import historical_accounting
    os.umask(0o077);OUT.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as td:
        tmp=Path(td);key,fp=_private_key_from_secret(tmp);need(fp==old.FP,'OWNER_KEY')
        parts=strict_json(file_at(route,state['ciphertext_path'],EVIDENCE));blob=restore_ciphertext(parts,lambda p:file_at(route,p,EVIDENCE))
        need(bytes_digest(blob)==state['ciphertext_sha256'],'PRESERVED_CIPHER')
        private=strict_json(unpack(owner.bounded_decrypt(blob,key,tmp)),max_elements=8000000);before=digest(private)
        need(private['sequence']==16 and private['safe_stop'] is True and private['source_sha']==state['source_sha'],'SEALED_CHECKPOINT')
        frozen=json.loads((ROOT/'V2_SEARCH_BUDGET_V1.json').read_bytes())
        need(frozen['v2_budget']==84 and frozen['unit']=='distinct V2 DEVELOPMENT economic identities whose economic outcome is opened','FROZEN_BUDGET_UNIT')
        budget=budget_projection(historical_accounting(ROOT),private)
        budget['source_sha256']={p:bytes_digest((ROOT/p).read_bytes()) for p in ('RESEARCH_CONTRACT_V2.md','V2_SEARCH_BUDGET_V1.json','research_v3/SEARCH_BUDGET_GOVERNANCE_V2.json','research_core_v4/laboratory/budgets.py','research_core_v4/laboratory/programs.py')}
        cache=DataCatalogue.restore(private['shared_catalogue'])
        c033,distribution=diagnose_c033(private['programmes'][PROGRAMME],cache)
        frontier,assets=inventory_and_frontier(route,corpus(key,tmp,registry()))
        need(digest(private)==before,'ORIGINAL_PRIVATE_STATE_MUTATED')
        result={'schema':'mxm.nonoutcome-reconciliation-private.v1','source_sha':os.environ['RECON_SOURCE_SHA'],'run_id':int(os.environ['GITHUB_RUN_ID']),
          'input_evidence_oid':EVIDENCE,'input_ciphertext_sha256':state['ciphertext_sha256'],'original_private_digest':before,
          'budget_reconciliation':budget,'C033_diagnostic':c033,'C033_distributions':distribution,'data_frontier':frontier,'data_inventory':assets,
          'new_outcomes':0,'new_identity_reservations':0,'broker_requests':0,'orders':0,'original_state_mutated':False}
        raw=encoded(result);pub=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem';need(public_spki_sha256(pub)==old.FP,'RECIPIENT')
        target=OUT/'diagnostic.mxmenc';encrypt_shard(gzip.compress(raw,mtime=0),public_key=pub,output=target)
        need(unpack(owner.bounded_decrypt(target.read_bytes(),key,tmp))==raw,'DIAGNOSTIC_ENCRYPTED_READBACK')
    anchors(route);need(route.json('git/ref/heads/mxm-o04-integrated-laboratory-evidence')['object']['sha']==EVIDENCE,'PARENT_MOVED')
    receipt={'schema':'mxm.nonoutcome-reconciliation-public.v1','source_sha':os.environ['RECON_SOURCE_SHA'],'run_id':int(os.environ['GITHUB_RUN_ID']),
      'trigger_sha':os.environ['GITHUB_SHA'],'input_evidence_oid':EVIDENCE,'input_sequence':16,'input_ciphertext_sha256':state['ciphertext_sha256'],
      'diagnostic_ciphertext_sha256':bytes_digest(target.read_bytes()),'budget_reconciliation':budget,'C033_diagnostic':c033,'data_frontier':frontier,
      'new_outcomes':0,'new_identity_reservations':0,'broker_requests':0,'orders':0,'original_state_mutated':False,
      'original_program_state_sha256':bytes_digest(file_at(route,'program-state.json',EVIDENCE)),
      'app_key_used':False,'active_authority_write':False,'safe_stop':True,'cbot_qualified':False}
    (OUT/'receipt.json').write_bytes(encoded(receipt));print(json.dumps(receipt,sort_keys=True))

def publish():
    need(os.environ['GITHUB_JOB']=='durable-reconciliation' and os.environ['GITHUB_RUN_ATTEMPT']=='1' and not os.environ.get('MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM') and not os.environ.get('SUCCESSOR_APP_PRIVATE_KEY'),'RECON_PUBLISH_NO_KEYS')
    route=GetOnly();anchors(route)
    data=ROOT/'verification/reconciliation-input';r=strict_json((data/'receipt.json').read_bytes());blob=(data/'diagnostic.mxmenc').read_bytes()
    allowed={'schema','source_sha','run_id','trigger_sha','input_evidence_oid','input_sequence','input_ciphertext_sha256','diagnostic_ciphertext_sha256','budget_reconciliation','C033_diagnostic','data_frontier','new_outcomes','new_identity_reservations','broker_requests','orders','original_state_mutated','original_program_state_sha256','app_key_used','active_authority_write','safe_stop','cbot_qualified'}
    need(set(r)==allowed,'RECON_PUBLIC_FIELDS')
    need(r['schema']=='mxm.nonoutcome-reconciliation-public.v1' and r['input_evidence_oid']==EVIDENCE and r['input_sequence']==16,'RECON_PUBLIC_BINDING')
    need(r['run_id']==int(os.environ['GITHUB_RUN_ID']) and r['source_sha']==os.environ['RECON_SOURCE_SHA'] and r['trigger_sha']==os.environ['GITHUB_SHA'],'RECON_NATIVE_BINDING')
    need(all(r[k]==0 for k in ('new_outcomes','new_identity_reservations','broker_requests','orders')) and all(r[k] is False for k in ('original_state_mutated','app_key_used','active_authority_write','cbot_qualified')),'RECON_SCOPE')
    need(blob.startswith(b'MXM_SHALLOW_M5_V2_ENC1\x00') and bytes_digest(blob)==r['diagnostic_ciphertext_sha256'],'RECON_ENCRYPTED_ARTIFACT')
    need(route.json('git/ref/heads/mxm-o04-integrated-laboratory-evidence')['object']['sha']==EVIDENCE,'RECON_PUBLISH_STALE')
    jobs=route.json('actions/runs/'+os.environ['GITHUB_RUN_ID']+'/jobs?per_page=100')['jobs']
    need(any(j['name']=='reconcile' and j['conclusion']=='success' for j in jobs),'RECON_NATIVE_WORKER_SUCCESS')
    need(bytes_digest(file_at(route,'program-state.json',EVIDENCE))==r['original_program_state_sha256'],'RECON_ORIGINAL_STATE')
    files,manifest=chunk_ciphertext(blob,PREFIX);files[PREFIX+'/checkpoint.parts.json']=encoded(manifest);files[PREFIX+'/receipt.json']=encoded(r)
    oid=atomic_publish(route,EVIDENCE,files,'Preserve nonoutcome accounting, original data frontier and sealed C033 feature diagnosis without changing checkpoint16')
    need(bytes_digest(file_at(route,'program-state.json',oid))==r['original_program_state_sha256'],'ORIGINAL_PROGRAM_STATE_CHANGED')
    restored=restore_ciphertext(strict_json(file_at(route,PREFIX+'/checkpoint.parts.json',oid)),lambda p:file_at(route,p,oid))
    need(restored==blob,'RECON_REMOTE_CIPHER_READBACK');anchors(route)
    print(json.dumps({'state':'NONOUTCOME_RECONCILIATION_DURABLE','evidence_oid':oid,'ciphertext_sha256':r['diagnostic_ciphertext_sha256'],'new_outcomes':0,'new_reservations':0,'original_checkpoint_sequence':16}))
if __name__=='__main__':
    import sys
    try:
        need(len(sys.argv)==2 and sys.argv[1] in ('worker','publish'),'MODE')
        worker() if sys.argv[1]=='worker' else publish()
    except Exception as e:
        print(json.dumps({'state':'NONOUTCOME_RECONCILIATION_SAFE_STOP','safe_code':str(e) if re.fullmatch(r'LAB_[A-Z0-9_]+',str(e)) else type(e).__name__}));raise SystemExit(1) from None
