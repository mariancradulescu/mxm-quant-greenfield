"""Independent GET-only evidence-granularity analysis, no privileged writer."""
import json,os,tempfile
from pathlib import Path
from .native import existing_summary,private_key,seal,OUT
from .control import need,digest,canonical
from research_core_v4.successor_c_20261018 import readback


def analyze(s):
    from research_core_v4.delegated_bc_20261019.science import partial_identification
    partial_identification(s)
    p=s['portfolio']
    need(type(p['selected']) is list and type(p['closed']) is list,'BC_READONLY_LEDGER_SCHEMA')
    return {'schema':'mxm.independent-evidence-granularity.v1',
        'accepted_source_summary_sha256':readback.SUMMARY_SHA,
        'accepted_design_sha256':readback.DESIGN_SHA,
        'saved_ledger_halt':p['halt'],
        'selected_records':len(p['selected']),'closed_records':len(p['closed']),
        'saved_uncertainty':s['uncertainty'],
        'saved_cost_terms':s['cost_terms'],
        'native_request_or_fill_receipts_in_this_summary':False,
        'analysis_of_saved_evidence_only':True,'price_feature_or_portfolio_replay':False,
        'causal_mechanism_identified':False,'independent_market_confirmation':False,
        'summary_integrity_does_not_establish_fill_provenance':True,'cbot_qualified':False}


def main():
    need(os.environ.get('GITHUB_REPOSITORY')=='mariancradulescu/mxm-quant-greenfield' and
         os.environ.get('GITHUB_REF_NAME')=='mxm-remediation-p0-p4-20261015-v1' and
         os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and
         os.environ.get('GITHUB_JOB')=='independent-evidence','BC_READONLY_WORKLOAD')
    need(not os.environ.get('SUCCESSOR_APP_PRIVATE_KEY'),'BC_READONLY_NO_APP_KEY')
    OUT.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as folder:
        tmp=Path(folder);key=private_key(tmp);result=analyze(existing_summary(key,tmp))
        blob=seal(result,key,tmp);(OUT/'independent-evidence.mxmenc').write_bytes(blob)
    receipt={'schema':'mxm.independent-evidence-public.v1','run_id':int(os.environ['GITHUB_RUN_ID']),
        'source_sha':os.environ['GITHUB_SHA'],'state':'ENCRYPTED_ANALYSIS_COMPLETE',
        'checkpoint_writer_used':False,'app_key_used':False,'broker_requests':0,'orders':0,
        'accepted_experiment_replays':0,'encrypted_sha256':digest(blob)}
    (OUT/'independent-public.json').write_bytes(canonical(receipt));print(json.dumps(receipt))

if __name__=='__main__':
    try:main()
    except Exception as error:
        import re
        code=str(error) if re.fullmatch(r'(BC|C)_[A-Z0-9_]+',str(error)) else type(error).__name__
        print(json.dumps({'state':'READONLY_STOP','safe_code':code}));raise SystemExit(1) from None
