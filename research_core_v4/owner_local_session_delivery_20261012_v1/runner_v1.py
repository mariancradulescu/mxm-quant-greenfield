"""Single use owner-authorized ciphertext rewrap only: no original market computations.

Secrets live only as GitHub Actions masked inputs. Only authenticated ciphertext is public.
"""
import os, json, pathlib, tempfile, subprocess, sys
from datetime import datetime, timezone
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.executable_coverage_diagnostic_v1.runner_v1 import relay

e=rt.e
P='research_core_v4/owner_local_session_delivery_20261012_v1/'
PHASE='SCOPE'

def need(test, code):
    e.w.old.need(bool(test), code)

def inventory(commit):
    return dict(z.split('\t',1)[::-1] for z in subprocess.check_output(
        ['git','ls-tree','-r',commit],cwd=e.a.ROOT,text=True).splitlines())

def gate():
    h=os.environ['GITHUB_SHA']
    a=json.loads((e.a.ROOT/(P+'EXECUTION_V1.json')).read_text())
    e.w.v2.runtime(h)
    need(a['authority']=='OWNER_STANDING_PEPPERSTONE_MACHINE_SIDE_READONLY_20261012','OWNER_SCOPE')
    need(a['stage']=='EXISTING_SUCCESS_NUMERIC_CIPHERTEXT_REWRAP_ONE_USE','STAGE')
    for f in ('broker_requests','orders','protected_forward','cloud_deployment',
              'new_external_sources','market_recalculation','alpha_promotion'):
        need(a[f] is False,'READ_ONLY_REWRAP_SCOPE')
    desired=e.w.old.REPO+'/.github/workflows/mxm-owner-local-secure-numeric-delivery-v1.yml@refs/heads/'+e.w.old.BRANCH
    need(os.environ.get('GITHUB_EVENT_NAME')=='push','PUSH_ONLY')
    need(os.environ.get('GITHUB_WORKFLOW_REF')==desired,'EXACT_WORKFLOW_ID')
    need(datetime.now(timezone.utc).isoformat()<a['expires_utc'],'ONE_USE_EXPIRED')
    need(e.w.old.api('git/ref/heads/'+e.w.old.BRANCH)['object']['sha']==h,'BRANCH_HEAD_DRIFT')
    e.a.ancestor(a['base_head'],h)
    orig,current=inventory(a['base_head']),inventory(h)
    need(all(current.get(p)==v for p,v in orig.items()),'FROZEN_FILES_UNCHANGED')
    for path,sha in a['bindings'].items():
        need(e.w.old.filehash(path)==sha,'SOURCE_HASH_BINDING')
    need(e.w.old.filehash(a['recipient_path'])==a['recipient_public_key_sha256'],'RECIPIENT_BINDING')
    e.w.old.verify_science()
    need(not e.w.v2.existing_ref(a['one_use_ref']),'ONE_USE_ALREADY_CONSUMED')
    e.w.old.api('git/refs',{'ref':'refs/tags/'+a['one_use_ref'],'sha':h})
    return h,a

def extract_existing(saved):
    need(saved['schema']=='mxm.private.native.decision.readback.20261012.v1','EXACT_SAVED_NUMERIC_SCHEMA')
    need(saved['source_head']=='962d1afc8918afdc6ad42759c659bc54aa48023e','ORIGINAL_SOURCE_HEAD')
    need(saved['source_one_use_recovery_head']=='39554ca653a162d27962f72f78ae17c9e86a9c3e','NUMERIC_SOURCE_HEAD')
    need(saved['existing_successful_recovery_run']==38239902202,'NUMERIC_SOURCE_RUN')
    need(saved['new_broker_requests']==0 and saved['new_trading_orders']==0,'READ_ONLY_SOURCE')
    data=saved['horizon_totals_and_sampled_weeks']
    need(len(data)==3 and [v['horizon_minutes'] for v in data]==[15,60,240],'EXACT_HORIZONS')
    need(all(len(z['sampled_iso_week_rows'])==40 for z in data),'SAMPLED_WEEK_CARDINALITY')
    for z in data:
        t=z['totals']
        need(0<=t['priced_eligible']<=t['structurally_rejected']+t['entry_admissible'],'COUNTS')
        need(t['weeks_optimistic_ge21_distinct_clocks']<=40,'WEEK_LIMIT')
    return {'schema':'mxm.private.owner.session.actual.numeric.decision.20261012.v1',
            'already_computed_from_run':38244279805,
            'source_private_result_run':38239902202,
            'source_head':saved['source_head'],
            'new_broker_requests':0,'new_market_computation':0,'orders':0,
            'sensitivity_scenario':saved['frozen_scenario'],
            'horizon_totals_and_sampled_iso_week_rows':data,
            'exclusion_reasons':saved['entry_exclusion_reasons'],
            'source_support':saved['source_support'],
            'local_horizon_classifications':saved['local_horizon_classifications'],
            'gross_cost_net_semantics':saved['gross_cost_net'],
            'hindsight_not_a_signal':saved['hindsight_opportunity'],
            'risk_limit':saved['risk_limit'],
            'HARD21':saved['HARD21'],
            'MAE_MFE':saved['MAE_MFE'],
            'historical_terms':saved['historical_terms'],
            'decision':'NO_ALPHA_PROMOTION;OPPORTUNITY_ONLY_NOT_CONSECUTIVE_REAL_TRADES'}

def selftest():
    sample={'schema':'mxm.private.native.decision.readback.20261012.v1',
            'source_head':'962d1afc8918afdc6ad42759c659bc54aa48023e',
            'source_one_use_recovery_head':'39554ca653a162d27962f72f78ae17c9e86a9c3e',
            'existing_successful_recovery_run':38239902202,
            'new_broker_requests':0,'new_trading_orders':0,
            'frozen_scenario':'S2_F010_DAY','entry_exclusion_reasons':{},'source_support':{},
            'local_horizon_classifications':{},'gross_cost_net':'HINDSIGHT',
            'hindsight_opportunity':'NOT_SIGNAL','risk_limit':'PROXY',
            'HARD21':'NOT_DEMONSTRATED','MAE_MFE':'UNAVAILABLE','historical_terms':'CURRENT_REFERENCE',
            'horizon_totals_and_sampled_weeks':[
                {'horizon_minutes':h,'totals':{'priced_eligible':1,'entry_admissible':1,'structurally_rejected':0,'weeks_optimistic_ge21_distinct_clocks':0},'sampled_iso_week_rows':[{}]*40}
                for h in (15,60,240)]}
    o=extract_existing(sample)
    assert len(o['horizon_totals_and_sampled_iso_week_rows'])==3
    assert o['new_market_computation']==0
    print('PASS_SYNTHETIC_ONLY_EXISTING_METRICS_EXTRACT_NO_BROKER',flush=True)

def main():
    global PHASE
    os.umask(0o077)
    h,a=gate()
    with tempfile.TemporaryDirectory(prefix='mxm-private-owner-delivery-',dir=os.environ['RUNNER_TEMP']) as temp:
        tmp=pathlib.Path(temp)
        PHASE='AUTHENTICATE_OWNER_ENCRYPTED_EXISTING_NUMERIC'
        key,fp=e.w.old._private_key_from_secret(tmp)
        need(fp==e.w.old.FP,'OWNER_KEY_FINGERPRINT')
        source,receipt=load_asset(key,fp,tmp,a['encrypted_source'])
        PHASE='SELECT_EXISTING_PRECOMPUTED_FIELDS_ONLY'
        result=extract_existing(source)
        result['input_ciphertext_provenance']=receipt
        PHASE='RSA_OWNER_SESSION_ENCRYPTED_RELAY'
        relay(h,a,tmp,result)
        print('PASS_OWNER_LOCAL_SESSION_EXISTING_NUMERIC_CIPHERTEXT_DELIVERED',flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['--selftest']:
        selftest()
    else:
        try:main()
        except Exception as error:
            rt.fail(error,PHASE)
            raise SystemExit(1) from None
