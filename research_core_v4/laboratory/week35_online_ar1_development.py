"""Finite dependent W35 online AR1 study. No broker interface or authority writer."""
import base64,gzip,json,os,subprocess
from decimal import Decimal as D
from pathlib import Path
from .common import bytes_digest,encoded,need
ROOT=Path(__file__).resolve().parents[2]
SPEC=ROOT/'research_core_v4/laboratory/WEEK35_ONLINE_AR1_DEVELOPMENT_V1.json'
SPEC_SHA='4fb321c8a3f3938440d161e4dd0320880726e9b9aa59651da1318556a4c79cbc'
LABEL='PINNED_PEPPERSTONE_WEEK35_ONLINE_AR1_STOP12_MODELED_TERMS_DEVELOPMENT_EXPOSED'
def validate_spec():
    raw=SPEC.read_bytes();need(bytes_digest(raw)==SPEC_SHA,'W35_PRECOMMIT_CHANGED')
    value=json.loads(raw)
    need(value['strategies']==['OnlineAr1'] and value['initial_capital_eur']==200 and
         value['slippage_quote_per_side']==[0.00002,0.00004] and
         value['budget']['mechanisms']==1 and value['budget']['dependent_model_leaves']==2 and
         value['orders']==0 and not value['confirmation_opened'] and not value['protected_opened'],
         'W35_FIXED_FINITE_SCOPE')
    kernel=ROOT/'research_core_v4/native_tick_replay_v1/csharp/MxmDecisionKernel.cs'
    need(bytes_digest(kernel.read_bytes())==value['kernel_sha256'],'W35_NO_KERNEL_REFIT')
    for path,expected in value['implementation_sha256'].items():
        need(bytes_digest((ROOT/path).read_bytes())==expected,'W35_FROZEN_IMPLEMENTATION_'+path)
    need(value['exit'].startswith('NeutralFlat') and value['learner']=={
        'window_pairs':256,'minimum_pairs':128,'ridge_bps_squared':64,'beta_clip':[-.95,.95],
        'signal_threshold_bps':2,'shock_reset_abs_return_bps':100,
        'intercept':'rolling meanY - beta * meanX',
        'cold_restart':'discard learned state, rewarm from newly completed bars; no learned-state persistence claim',
        'gap':'reset shared causal strategy state on noncontiguous bars',
        'configuration_selection':'engineering priors frozen before new outputs; not estimated from W35',
        'positive_result_is_confirmed':False},'W35_FIXED_LEARNING_RULE')
    return value

def context():
    validate_spec()
    need(os.environ.get('GITHUB_REPOSITORY')=='mariancradulescu/mxm-quant-greenfield' and
         os.environ.get('GITHUB_REF')=='refs/heads/mxm-remediation-p0-p4-20261015-v1' and
         os.environ.get('GITHUB_EVENT_NAME') in ('push','workflow_dispatch') and
         os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and
         os.environ.get('GITHUB_WORKFLOW_REF')=='mariancradulescu/mxm-quant-greenfield/.github/workflows/mxm-week35-online-ar1-development.yml@refs/heads/mxm-remediation-p0-p4-20261015-v1' and
         os.environ.get('LAB_CHRONOLOGY_PROFILE')=='W35','W35_PROTECTED_NATIVE_CONTEXT')
    sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    need(sha==os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA') and
         subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0,'W35_CLEAN_EXACT_NATIVE_SOURCE')
    need(not any(os.environ.get(k) for k in ('SUCCESSOR_APP_PRIVATE_KEY','R3_CTRADER_ACCESS_TOKEN',
         'R3_CTRADER_CLIENT_ID','R3_CTRADER_CLIENT_SECRET','R3_CTRADER_REFRESH_TOKEN')),'W35_NO_WRITER_OR_BROKER_SECRET')
    return sha

def disposition(equities):
    need(len(equities)==2 and all(x.is_finite() for x in equities),'W35_TWO_FINITE_DEPENDENT_RESULTS')
    return ('REJECT_THIS_FIXED_DEVELOPMENT_CONFIGURATION' if all(x<=D(200) for x in equities) else
            'INCONCLUSIVE_REQUIRES_INDEPENDENT_AFTER_COST_VALIDATION')

def finalize(tmp,out):
    sha=context();tmp=Path(tmp);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    bridge=json.loads((tmp/'ticks.ndjson.receipt.json').read_bytes())
    need(bridge['source_run']==39946364621 and bridge['iso_week']=='2026-W35' and
         bridge['verified_bid_events']==341578 and bridge['verified_ask_events']==341444 and
         bridge['derived_ticks_sha256']==bytes_digest((tmp/'ticks.ndjson').read_bytes()) and
         bridge['orders']==bridge['fills']==0 and not bridge['historical_costs_proven'],
         'W35_AUTHENTIC_BRIDGE_BINDING')
    full={'schema':'mxm.week35.online-ar1-private-result.v1','spec_sha256':SPEC_SHA,'native_source_commit':sha,
          'bridge':bridge,'models':{},'benchmark_eur':200,'capital_is_shared_across_scenarios':False,
          'scenarios_are_alternatives_not_concurrent_accounts':True}
    verdicts={}
    for family in ('OnlineAr1',):
        full['models'][family]={};equities=[]
        for scenario,slip in (('base',D('.00002')),('stress',D('.00004'))):
            folder=tmp/family/scenario;reportbytes=(folder/'portfolio-exposed-quote-readback.json').read_bytes()
            report=json.loads(reportbytes,parse_float=D)
            mark=json.loads((folder/'independent-mark.json').read_bytes())
            p=report['modeled_parameters'];a=report['account']
            need(report['classification']==LABEL and report['quote_events']==683022 and
                 report['original_native_run_id']==39946364621 and
                 report['derived_stream_sha256']==bridge['derived_ticks_sha256'] and
                 report['captured_terms_sha256']==bridge['captured_symbol_terms_sha256'] and
                 p['strategy']==family and p['exit_policy']=='NeutralFlat' and p['online_ar1'] is True and D(str(p['slip_price_per_side']))==slip and
                 p['units']==1000 and p['bar_minutes']==5 and p['max_positions']==1 and
                 p['product_default_stop12'] is True and D(str(p['product_stop_distance_quote']))==D('.0012') and
                 a['initial_capital_eur']==200 and a['complete_iso_utc_weeks']==0 and
                 not a['hard21_proven'] and not a['broker_fills_proven'] and not a['costs_broker_verified'] and
                 not report['scientific_confirmation_opened'] and report['live_orders']==report['new_broker_requests']==0,
                 'W35_FIXED_MODEL_OR_AUTHORITY_CHANGED')
            need(mark['product_default_stop12_replayed'] and mark['captured_commission_component_checked'] and
                 mark['quote_side_fx_conversion_checked'] and
                 D(mark['cash_abs_difference_eur'])<D('.000001') and
                 D(mark['equity_abs_difference_eur'])<D('.000001') and not mark['hard21'] and
                 mark['terminal_open_stop_paths_independently_checked']==a['open_positions'],
                 'W35_INDEPENDENT_ACCOUNT_AND_STOP_CHECKS')
            equity=D(str(a['marked_equity_eur']));equities.append(equity)
            gross=sum((D(str(e['gross_eur'])) for e in a['ledger']),D(0))
            fees=sum((D(str(e['commission_eur'])) for e in a['ledger']),D(0))
            full['models'][family][scenario]={'original_report_bytes_b64':base64.b64encode(reportbytes).decode(),
                'independent_mark':mark,'gross_realized_eur':str(gross),'fees_paid_eur':str(fees),
                'terminal_quote_side_equity_eur':str(equity),'change_from_cash_eur':str(equity-D(200)),
                'entries':a['accepted_entries'],'exits':a['executed_exits'],
                'drawdown_eur':str(a['max_drawdown_eur']),'terminal_open_positions':a['open_positions']}
        verdicts[family]=disposition(equities)
    verdict=('ONLINE_AR1_FIXED_CONFIGURATION_DOES_NOT_ADVANCE' if all(v.startswith('REJECT_') for v in verdicts.values()) else
             'INCONCLUSIVE_NO_CONFIRMED_EDGE')
    full['disposition']=verdict;full['family_dispositions']=verdicts
    from research_core_v4.shallow_m5_support_v2_production import encrypt_shard,public_spki_sha256
    from research_core_v4.successor_c_20261018.readback import FP
    public=ROOT/'research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem'
    need(public_spki_sha256(public)==FP,'W35_EXISTING_ENCRYPTION_RECIPIENT')
    raw=encoded(full);encrypt_shard(gzip.compress(raw,mtime=0),public_key=public,output=out/'full-result.mxmenc')
    receipt={'schema':'mxm.week35.online-ar1-public-result.v1','native_source_commit':sha,
        'run_id':int(os.environ['GITHUB_RUN_ID']),'source_run':39946364621,'spec_sha256':SPEC_SHA,
        'source_ciphertext_sha256':bridge['ciphertext_sha256'],'source_private_sha256':bridge['private_sha256'],
        'derived_ticks_sha256':bridge['derived_ticks_sha256'],'dependent_model_leaves':2,'mechanisms':1,
        'partition':'DEVELOPMENT_ALREADY_M5_EXPOSED','disposition':verdict,'family_dispositions':verdicts,'edge_confirmed':False,
        'hard21_proven':False,'native_ctrader_fills_proven':False,'historical_costs_proven':False,
        'independent_confirmation':False,'canonical_V2_ledger_mutated':False,'C033_reservation_preserved':True,
        'orders':0,'new_broker_requests':0,'cloud_activated':False,'full_private_sha256':bytes_digest(raw),
        'result_ciphertext_sha256':bytes_digest((out/'full-result.mxmenc').read_bytes())}
    (out/'receipt.json').write_bytes(encoded(receipt))
    print('MXM_W35_ONLINE_AR1_DEVELOPMENT '+json.dumps(receipt,sort_keys=True),flush=True)
    return receipt

if __name__=='__main__':
    import sys
    os.umask(0o077)
    if sys.argv[1:] == ['admit']:
        context();print('MXM_W35_ONLINE_AR1_PRECOMMIT_ADMITTED_DEVELOPMENT_ONLY')
    else:
        need(len(sys.argv)==3,'W35_FINALIZE_ARGUMENTS');finalize(sys.argv[1],sys.argv[2])
