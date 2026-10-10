"""Reduce saved qualification receipts only; no acquisition or qualification replay."""
import os,json,pathlib,tempfile,subprocess,hashlib,base64
from datetime import datetime,timezone
from collections import Counter
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.executable_coverage_diagnostic_v1.runner_v1 import relay,summarize
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4 import shallow_m5_support_v2 as v2
from m6.ctrader_proto.OpenApiCommonMessages_pb2 import ProtoMessage
e=rt.e;P='research_core_v4/native_executable_qualification_v1/';PHASE='GATE'
def need(x,c):e.w.old.need(bool(x),c)
def main():
    global PHASE
    h=os.environ['GITHUB_SHA'];e.w.v2.runtime(h);a=json.loads((e.a.ROOT/(P+'RECEIPT_READBACK_EXECUTION_V1.json')).read_text())
    need(a['authority']=='EXPLICIT_OWNER_SAVED_NATIVE_RECEIPT_CAUSE_READBACK_ONLY' and not any(a[k] for k in ('orders','protected_forward','cloud_deployment','broker_requests','scientific_replay')),'SCOPE')
    need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-native-qualification-receipt-readback-v1.yml@refs/heads/'+e.w.old.BRANCH,'WORKFLOW')
    need(datetime.now(timezone.utc).isoformat()<a['expires_utc'],'EXPIRED');e.a.ancestor(a['base_head'],h)
    for p,s in a['bindings'].items():need(e.w.old.filehash(p)==s,'SOURCE_BINDING')
    inv=lambda r:dict(line.split('\t',1)[::-1] for line in subprocess.check_output(['git','ls-tree','-r',r],cwd=e.a.ROOT,text=True).splitlines());old=inv(a['base_head']);new=inv(h);need(all(new.get(p)==s for p,s in old.items()),'UNCHANGED_QUALIFICATION')
    need(not e.w.v2.existing_ref(a['one_use_ref']),'CONSUMED');e.w.old.api('git/refs',{'ref':'refs/tags/'+a['one_use_ref'],'sha':h})
    with tempfile.TemporaryDirectory(prefix='mxm-native-receipt-readback-',dir=os.environ['RUNNER_TEMP']) as td:
        tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'OWNER_KEY');PHASE='EXISTING_ENCRYPTED_PRIMARY';old,op=load_asset(key,fp,tmp,a['qualification_source']);cost,cp=load_asset(key,fp,tmp,a['cost_source']);native=cost['current_native_evidence']['private_native_evidence'];episodes=old['private_qualification_episodes'];need(len(episodes)==240,'SAVED_EPISODES')
        causes=Counter();ids={s:Counter() for s in (1,2,250)};details=[]
        for q in old['private_quote_receipts']:
            sides=q['sides'];missing=any(sides[k].get('state')!='AUTHENTIC_CAUSAL_QUOTE' for k in ('bid','ask'));truncated=any(sides[k].get('source_has_more',False) for k in ('bid','ask'))
            stale=not missing and any(sides[k]['age_ms']>5000 for k in ('bid','ask'));skew=None if missing else abs(sides['bid']['timestamp_ms']-sides['ask']['timestamp_ms']);crossed=not missing and not 0<sides['bid']['price']<=sides['ask']['price']
            reason='MISSING_SIDE' if missing else 'HAS_MORE' if truncated else 'INVALID_OR_CROSSED_PRICE' if crossed else 'LAST_SIDE_TICK_AGE_GT5S' if stale else 'SIDE_TIMESTAMPS_DIFFER_GT2S' if skew>2000 else 'VALID'
            causes[reason]+=1;ids[q['symbol_id']][reason]+=1
            if reason!='VALID':details.append({'sid':q['symbol_id'],'boundary_ms':q['boundary_ms'],'reason':reason,'ages_ms':{k:sides[k].get('age_ms') for k in sides},'side_skew_ms':skew,'tick_timestamp_meaning':'LAST_OBSERVED_SIDE_TICK_TIMESTAMP_NOT_CERTIFIED_CONTEMPORANEOUS_EXECUTABLE_SNAPSHOT_TIMESTAMP'})
        need(causes['VALID']==old['summary']['quote_quality']['VALID_FRESH_UNPAGED_SYNCHRONIZED'],'BOUNDARY_CONSERVATION');m5stats=[]
        for r in old['private_m5_acquisition_receipts']:
            env=ProtoMessage();env.ParseFromString(base64.b64decode(r['raw_response_envelope_b64'],validate=True));res=v2.ProtoOAGetTrendbarsResV2();res.ParseFromString(env.payload)
            need(res.IsInitialized() and res.period==v2.M5_ENUM and (not res.HasField('symbolId') or res.symbolId==r['sid']),'SAVED_RAW_RESPONSE_BINDING');times=[int(b.utcTimestampInMinutes)*60000 for b in res.trendbar]
            need(sum(t<r['from_ms'] for t in times)==r['lower_boundary_overfetch_discarded'] and sum(r['from_ms']<=t<=r['to_ms'] for t in times)==len(r['rows']),'RAW_VS_SAVED_BAR_CONSERVATION')
            m5stats.append({'sid':r['sid'],'requested_from_ms':r['from_ms'],'requested_to_ms':r['to_ms'],'raw_returned_rows':len(times),'within_requested_interval':len(r['rows']),'discarded_before_from':r['lower_boundary_overfetch_discarded'],'decoder_diagnostic':r['decoder_diagnostic'],'raw_first_ms':min(times),'raw_last_ms':max(times),'has_more_present':r['has_more_present'],'has_more':r['has_more'],'pagination_reason':r['pagination_reason'],'roundtrip_latency_ms':r['roundtrip_latency_ms'],'raw_envelope_sha256':hashlib.sha256(base64.b64decode(r['raw_response_envelope_b64'])).hexdigest(),'rows_sha256':r['canonical_rows_sha256']})
        split=[];econ=Counter()
        for r in episodes:
            if r['joint'] and not r['current_economic_pass']:
                if r['risk_proxy_plus_cost_eur']>2:why='PRE_ENTRY_H1_RANGE_PLUS_CURRENT_COST_STRESS_GT2EUR'
                elif r['current_minimum_margin_eur']>50 or r['current_free_capital_eur']<150:why='CURRENT_MARGIN_GATE'
                else:why='OTHER_CURRENT_ECONOMIC_GATE'
                econ[why]+=1
        for sid in (1,2,250):
            for horizon in (3600,14400):
                for clock in ('09:15','13:15'):
                    rr=[r for r in episodes if r['sid']==sid and r['horizon_seconds']==horizon and r['entry_clock']==clock];split.append({'sid':sid,'horizon_seconds':horizon,'entry_clock':clock,'calendar':len(rr),'joint':sum(r['joint'] for r in rr),'current_economic_pass':sum(r['current_economic_pass'] for r in rr),'not_a_new_selection_or_promotion':True})
        contracts=[]
        for sid in (1,2,250):
            full=native['full'][str(sid)];contracts.append({'sid':sid,'current_native_extra_fields':{k:full.get(k) for k in ['slDistance','tpDistance','distanceSetIn','swapCalculationType','swapTime','swapPeriod','swapRollover3Days','rolloverCommission','pnlConversionFeeRate']},'dated_historical_economic_contract':'UNAVAILABLE_NOT_ZERO'})
        out={'schema':'mxm.private.native.saved.receipt.cause.readback.v1','source_head':h,'qualification_source_head':old['summary']['source_head'],'qualification_provenance':op,'cost_provenance':cp,'saved_decision':old['summary']['decision'],'saved_quote_causes':dict(causes),'quote_causes_by_identity':{str(s):dict(v) for s,v in ids.items()},'private_invalid_boundary_details':details,'saved_m5_response_diagnostics':m5stats,'saved_economic_exclusions':dict(econ),'saved_clock_support':split,'current_native_extra_contract':contracts,'new_broker_requests':0,'qualification_rules_changed':False,'qualification_or_directional_results_recomputed':False,'orders':0,'protected_forward':False,'cloud_deployment':False,'interpretation':'LAST_PRICE_CHANGE_AGE_AND_SIDE_SKEW_PROXY_FAILS_ARE_NOT_PROOF_OF_MISSING_BROKER_HISTORY_OR_UNTRADEABILITY;DO_NOT_RELAX_FROZEN_RULES_RETROSPECTIVELY'}
        PHASE='ENCRYPTED_RECEIPT_DELIVERY';rt.output(h,a,tmp,key,'nativereceipts',{'summary':out},out);relay(h,a,tmp,out)
if __name__=='__main__':
    try:main()
    except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(2) from None
