"""Authenticated final aggregate readback. No broker, forecasts or exit-kernel calls."""
import json,os,pathlib,tempfile,statistics,subprocess
from collections import Counter,defaultdict
from datetime import datetime,timezone
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.executable_coverage_diagnostic_v1.runner_v1 import relay
e=rt.e;P='research_core_v4/dynamic_exit_diagnostic_v1/';PHASE='READBACK_GATE'
def need(x,c):e.w.old.need(bool(x),c)
def aggregate(v):
 v=list(v);return {'N':len(v),'sum':sum(v) if v else None,'median':statistics.median(v) if v else None,'mean':statistics.mean(v) if v else None,'min':min(v) if v else None,'max':max(v) if v else None}
def reduce(full,old):
 records=full['records'];summary=full['summary'];params={(r['sid'],r['t'],r['h']):r['value'] for r in full['source_parameters']};saved={(r['sid'],r['t'],r['h']):r for r in old['events'] if r['family']=='NATIVE_NET_SIDE_COST_CONDITIONING_V1' and r['model_admit']};selected={(r['sid'],r['t'],r['h']) for r in full['frozen_selection']};out={};weekly={};reasons={};scenarios={}
 for name in sorted({r['policy'] for r in records}):
  z=[r for r in records if r['policy']==name and (r['sid'],r['t'],r['h']) in selected];valid=[r for r in z if r.get('accounts',{}).get('S2_F010_DAY') is not None]
  out[name]={'selected':len(z),'dynamic_NET_evaluable':len(valid),'exit_reasons':dict(Counter(r.get('reason',r['state']) for r in z)),'unknown_states':dict(Counter(r['state'] for r in z if r not in valid)),'holding_minutes':aggregate((r['exit']-r['t'])/60 for r in valid),'MFE_entry_FX_reference_eur':aggregate(r['MFE_reference_eur'] for r in valid),'MAE_entry_FX_reference_eur':aggregate(r['MAE_reference_eur'] for r in valid),'native_account_components':{n:aggregate(r['accounts']['S2_F010_DAY'][n] for r in valid) for n in ('gross_eur','entry_commission_eur','exit_commission_eur','pnl_conversion_fee_eur','funding_stress_eur','net_eur')},'observed_fresh_pair_gaps_over5min':aggregate(r.get('observed_fresh_pair_gaps_over5min',0) for r in valid),'actual_fill_count':0}
  weekly[name]={};ww=defaultdict(list)
  for r in valid:ww[datetime.fromtimestamp(r['t'],timezone.utc).strftime('%G-W%V')].append(r)
  for w,rr in sorted(ww.items()):weekly[name][w]={'dynamic_evaluable':len(rr),'dynamic_NET_eur':sum(r['dynamic_net'] for r in rr),'mean_NET_eur':statistics.mean(r['dynamic_net'] for r in rr),'positive_NET':sum(r['dynamic_net']>0 for r in rr)}
  scenarios[name]={}
  for scenario in summary['dynamic_sensitivity_totals'][name]:
   paired=[];costs=[]
   for r in z:
    original=saved[r['sid'],r['t'],r['h']];fixed=original['accounts'][scenario][0 if r['side']>0 else 1];dynamic=r.get('accounts',{}).get(scenario)
    if dynamic is not None:costs.append(dynamic)
    if fixed is not None and dynamic is not None:paired.append((dynamic['net_eur'],fixed['net_eur']))
   scenarios[name][scenario]={'dynamic_evaluable':len(costs),'dynamic_NET_eur':sum(x['net_eur'] for x in costs) if costs else None,'paired_same_entries':len(paired),'paired_dynamic_NET_eur':sum(x[0] for x in paired) if paired else None,'paired_fixed_NET_eur':sum(x[1] for x in paired) if paired else None,'paired_increment_eur':sum(x[0]-x[1] for x in paired) if paired else None}
 unique=defaultdict(set)
 for sid,t,h in saved:unique[datetime.fromtimestamp(t,timezone.utc).strftime('%G-W%V')].add((sid,t))
 selection=[params[key] for key in selected];risk={'saved_stress_eligible':sum(v and v['stress_eligible'] for v in params.values()),'selected_stress_risk_eur':aggregate(v['stress_risk_eur'] for v in selection),'selected_current_margin_eur':aggregate(saved[key]['entry']['margin_eur'] for key in selected),'selected_entry_all_in_cost_eur':aggregate(saved[key]['entry']['cost_eur'] for key in selected)}
 reuse={'existing_bid_tick_rows':sum(v['existing_reuse_audit']['bid']['existing_decoded_ticks'] for v in summary['tick_path_reports']),'existing_ask_tick_rows':sum(v['existing_reuse_audit']['ask']['existing_decoded_ticks'] for v in summary['tick_path_reports']),'complete_old_windows_ms_per_side':sum(v['existing_reuse_audit']['bid']['existing_complete_window_ms'] for v in summary['tick_path_reports']),'new_requests_exclude_complete_old_windows':True}
 return {'schema':'mxm.private.dynamic.exit.final.aggregate.readback.v1','numeric_source_head':summary['source_head'],'numeric_summary_sha256':e.a.sha(e.a.enc(summary)),'numeric_source_run':38209738609,'numeric_source_job':114681005113,'classification':'DEVELOPMENT_NOT_INDEPENDENT_CONFIRMATION','mechanism_aggregates':out,'weekly_dynamic_NET':weekly,'paired_sensitivity':scenarios,'weekly_unique_saved_instrument_entries':{w:len(z) for w,z in sorted(unique.items())},'risk_reference':risk,'existing_tick_reuse':reuse,'portfolio_week_counts':{h:{name:{slots:{which:{n:v for n,v in item.items() if n in ('selected_by_week','closed_by_exit_week','selected','closed','halt','cash_closed_accounting_eur')} for which,item in pair.items()} for slots,pair in ss.items()} for name,ss in pp.items()} for h,pp in summary['portfolio'].items()},'requests_original_numeric_stage':summary['requests'],'mission_total_BID_ASK':summary['mission_total_BID_ASK'],'new_broker_requests':0,'new_predictive_calls':0,'exit_kernel_calls':0,'scientific_limits':['MFE_MAE_AT_ENTRY_FX_REFERENCE_NOT_DATED_INTRATRADE_CONVERSION','NO_FILL_LATENCY_OR_STOP_EXECUTION_GUARANTEE','CONTINUOUS_SIGNAL_COVERAGE_UNKNOWN','STATIC_BRACKET_ALSO_SUBJECT_TO_IMPLEMENTED_M5_UPDATE_BAR_FILTER;THREE_RESULTS_CENSORED_NOT_PROVEN_UNTRADEABLE'],'alpha_certified':False,'HARD21':False,'Cloud_changes':False,'verdict':'INSUFICIENT_DATE;NEGATIVE_NET_ON_BOUNDED_DYNAMIC_TRANCHE'}
def main():
 global PHASE
 os.umask(0o077);head=os.environ['GITHUB_SHA'];auth=json.loads((e.a.ROOT/(P+'FINAL_READBACK_EXECUTION_V1.json')).read_text());e.w.v2.runtime(head);need(auth['authority']=='EXPLICIT_OWNER_SAME_MISSION_FINAL_SECURE_READBACK_20261012','READBACK_SCOPE');need(not any(auth[n] for n in ('orders','protected_forward','broker_requests','scientific_kernel_replay','cloud_changes')),'READ_ONLY_SCOPE');need(os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-dynamic-exit-final-readback-v1.yml@refs/heads/'+e.w.old.BRANCH,'READBACK_WORKFLOW');need(datetime.now(timezone.utc).isoformat()<auth['expires_utc'],'EXPIRED')
 for path,sha in auth['bindings'].items():need(e.w.old.filehash(path)==sha,'READBACK_BINDING')
 e.a.ancestor(auth['numeric_head'],head);old=subprocess.check_output(['git','ls-tree','-r',auth['numeric_head']],cwd=e.a.ROOT,text=True).splitlines();new=set(subprocess.check_output(['git','ls-tree','-r',head],cwd=e.a.ROOT,text=True).splitlines());need(all(v in new for v in old),'ALL_OLD_FILES_PRESERVED');need(not e.w.v2.existing_ref(auth['one_use_ref']),'ONE_USE');e.w.old.api('git/refs',{'ref':'refs/tags/'+auth['one_use_ref'],'sha':head})
 with tempfile.TemporaryDirectory(prefix='mxm-exit-final-readback-',dir=os.environ['RUNNER_TEMP']) as td:
  tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'OWNER_KEY');PHASE='READ_AUTHENTIC_EXISTING_RESULTS';full,proof=load_asset(key,fp,tmp,auth['numeric_source']);old,oldproof=load_asset(key,fp,tmp,auth['original_saved_signal_source']);need(full['summary']['source_head']==auth['numeric_head'],'SAVED_NUMERIC_HEAD');PHASE='REDUCE_SAVED_ACCOUNTING_ONLY';report=reduce(full,old);report.update(readback_source_head=head,source_provenance=[proof,oldproof],independent_acceptance_claimed=False);PHASE='ENCRYPTED_FINAL_READBACK';rt.output(head,auth,tmp,key,'exitfinalreadback',report,report);relay(head,auth,tmp,report)
if __name__=='__main__':
 try:main()
 except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(1)
