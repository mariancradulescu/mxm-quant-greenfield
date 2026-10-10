"""Additional saved-field cause disaggregation; never recomputes H1 or returns."""
import os,json,pathlib,tempfile,subprocess
from collections import Counter,defaultdict
from datetime import datetime,timezone
from research_core_v4.executable_coverage_diagnostic_v1.runner_v1 import relay,point,iso
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
e=rt.e;P='research_core_v4/executable_coverage_diagnostic_v1/';PHASE='GATE'
def need(x,c):e.w.old.need(bool(x),c)
def classification(r):
    reason=r['economics']['reason']
    if reason!='ECONOMIC_REFERENCE_OR_RANGE_UNAVAILABLE':return reason
    p=r['causal_reference_price'];width=r['causal_h1_range']
    if p is None:return 'LATEST_COMPLETED_M5_REFERENCE_MISSING_OR_INVALID'
    if p<=0:return 'LATEST_COMPLETED_M5_REFERENCE_NONPOSITIVE'
    if width is None:return 'PREVIOUS_H1_BASELINE_UNAVAILABLE_WITH_VALID_LATEST_M5_REFERENCE'
    if width<=0:return 'PREVIOUS_H1_RANGE_NONPOSITIVE'
    raise RuntimeError('UNEXPLAINED_SAVED_REFERENCE_REASON')
def main():
    global PHASE
    os.umask(0o077);h=os.environ['GITHUB_SHA'];e.w.v2.runtime(h);a=json.loads((e.a.ROOT/(P+'FIELD_READBACK_EXECUTION_V1.json')).read_text())
    need(a['authority']=='EXPLICIT_OWNER_PRECISE_EXISTING_DIAGNOSTIC_FIELD_READBACK_20261010' and not any(a[k] for k in ('orders','protected_forward','cloud_deployment','broker_requests','scientific_replay')),'SCOPE')
    need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-executable-field-readback-v1.yml@refs/heads/'+e.w.old.BRANCH,'WORKFLOW')
    need(datetime.now(timezone.utc).isoformat()<a['expires_utc'],'EXPIRED');e.a.ancestor(a['base_head'],h)
    for p,s in a['bindings'].items():need(e.w.old.filehash(p)==s,'SOURCE_BINDING')
    inventory=lambda ref:dict(line.split('\t',1)[::-1] for line in subprocess.check_output(['git','ls-tree','-r',ref],cwd=e.a.ROOT,text=True).splitlines())
    old=inventory(a['base_head']);new=inventory(h);need(all(new.get(p)==s for p,s in old.items()),'PRESERVED_BASE')
    need(not e.w.v2.existing_ref(a['one_use_ref']),'CONSUMED');e.w.old.api('git/refs',{'ref':'refs/tags/'+a['one_use_ref'],'sha':h})
    with tempfile.TemporaryDirectory(prefix='mxm-saved-fields-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'KEY')
        PHASE='EXISTING_ENCRYPTED_FIELDS';activity,ap=load_asset(key,fp,tmp,a['activity_source']);cost,cp=load_asset(key,fp,tmp,a['cost_source']);quotes,qp=load_asset(key,fp,tmp,a['quote_source'])
        trials=activity['private_all_trials'];need(len(trials)==171024,'SAVED_TRIALS');globalcauses=Counter();blocks=[Counter() for _ in range(4)];weeks=defaultdict(Counter);ids=defaultdict(Counter)
        for r in trials:
            why=classification(r);globalcauses[why]+=1;blocks[r['block']][why]+=1;weeks[r['iso']][why]+=1;ids[r['sid']][why]+=1
        need(sum(globalcauses.values())==171024,'CONSERVATION')
        master=e.w.old.verify_science()[0];masterids={r['symbol_id'] for r in master};metadata={r['broker_symbol']:r for r in cost['metadata_rows']}
        fields=('symbol_id','broker_symbol','asset_class','product_type','base_asset','quote_asset','buy_eligible_current','sell_eligible_current','buy_margin_eur','sell_margin_eur','min_volume_cents','step_volume_cents','lot_size','max_volume_cents','commission_rate_normalized','commission_rate_unit','min_commission_normalized','min_commission_type','min_commission_asset','pnl_conversion_fee_pct','swap_long','swap_short','swap_calculation_type','swap_period','swap_time','swap_rollover_3_days','schedule_time_zone','source')
        native=[]
        for name in ('EURUSD','GBPUSD','SpotCrude'):
            row=metadata.get(name)
            if row is None:native.append({'symbol':name,'current_native_metadata':'ABSENT'});continue
            sid=int(row['symbol_id']);qq=[q for q in quotes['private_boundary_receipts'] if q['symbol_id']==sid]
            native.append({'symbol':name,'current_contract':{f:row.get(f) for f in fields},'in_existing_MASTER1576_M5_identity_set':sid in masterids,'existing_boundary_receipts':len(qq),'existing_fresh_unpaged_two_sided_boundaries':sum(point(q) is not None for q in qq)})
        out={'schema':'mxm.private.saved.executable.field.cause.readback.v1','source_head':h,'input_provenance':[ap,cp,qp],
          'calendar':len(trials),'saved_evaluation_cause_disaggregation':dict(globalcauses),'original_blocks':[dict(v) for v in blocks],'ISO_UTC':{k:dict(v) for k,v in weeks.items()},'identity_causes':[{'sid':sid,'causes':dict(v)} for sid,v in sorted(ids.items())],
          'owner_fixed_three_native_symbol_inventory':native,
          'evidence_limit':'LATEST_REFERENCE_AND_H1_BASELINE_FLAGS_ARE_SAVED_FIELDS;NO_RAW_M5_OPENED;MISSING_VS_INVALID_BAR_INSIDE_PREVIOUS_H1_NOT_DISTINGUISHABLE_FROM_SAVED_FIELDS;NO_CLAIM_OF_ALL_OTHER_ARCHIVE_ABSENCE',
          'hourly_non_evaluation_disaggregation':'NOT_PERSISTED_IN_PRIMARY;NO_REPLAY_TO_RECONSTRUCT',
          'closed_source_head':'98e0421317a16726d54f31ff9a0a9f98563fa85f','signal_model_label_return_or_PnL_recalculated':False,'broker_requests':0,'orders':0,'protected_forward':False,'cloud_deployment':False,'new_directional_experiment':False,'robust_NET':False,'HARD21':False}
        PHASE='OWNER_ENCRYPTED_DELIVERY';rt.output(h,a,tmp,key,'executablefields',{'summary':out},out)
        PHASE='SESSION_RELAY';relay(h,a,tmp,out)
if __name__=='__main__':
    try:main()
    except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(2) from None
