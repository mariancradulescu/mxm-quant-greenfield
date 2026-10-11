"""Complete only locally blocked frozen quotes; reuse stored forecasts, no H1/model replay."""
import os,json,tempfile,pathlib,subprocess,hashlib
from collections import Counter,defaultdict
from datetime import datetime,timezone
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.executable_coverage_diagnostic_v1.runner_v1 import relay
from research_core_v4.wide_greenfield_v1.collect_v2 import Collector
from research_core_v4.wide_greenfield_v1 import economics_v1 as econ,kernel_v1 as k
from research_core_v4.wide_greenfield_v1.runner_v1 import slim_econ
e=rt.e;P='research_core_v4/wide_greenfield_v1/';PHASE='GATE'
def need(x,c):e.w.old.need(bool(x),c)
class TickOnlyCompletion(Collector):
 def send(self,req,historical=False):
  need(type(req).__name__=='ProtoOAGetTickDataReq','ONLY_FROZEN_MISSING_TICK_REQUESTS');need(self.counts['tick']<10000,'FROZEN_TICK_SIDE_CAP');self.hrate.before_send();self.counts['tick']+=1;return self.tr.request(req,timeout=30)
def correct_feature_count(node):
 if isinstance(node,dict):
  if 'feature_valid' in node and 'calendar' in node and 'abstention_reasons' in node:node['feature_valid_raw_nonnull_packed_flag']=node['feature_valid'];node['feature_valid']=node['calendar']-node['abstention_reasons'].get('FEATURE_GAP',0)
  for x in list(node.values()):correct_feature_count(x)
 elif isinstance(node,list):
  for x in node:correct_feature_count(x)

def magnitude_quote_envelope(cohort,rows,cat,quotes):
 byid={r['sid']:r for r in rows};g=econ.graph(rows);parts=[]
 for ev in cohort:
  r=byid[ev['sid']];f=cat['full'][str(r['sid'])];t=ev['t']+300
  for scenario,(slip,funding,absolute) in econ.SCENARIOS.items():
   a=econ.account(1,r,f,t,t+7200,2,quotes,g,slip,funding,absolute);b=econ.account(-1,r,f,t,t+7200,2,quotes,g,slip,funding,absolute)
   parts.append({'sid':r['sid'],'iso':ev['iso'],'scenario':scenario,'long':a,'short':b})
 def report(rr):
  out={}
  for s in econ.SCENARIOS:
   vv=[x for x in rr if x['scenario']==s and x['long'] is not None and x['short'] is not None];n=len(vv);out[s]={'N':n,'long_net_sum_eur':sum(x['long']['net_eur'] for x in vv) if n else None,'short_net_sum_eur':sum(x['short']['net_eur'] for x in vv) if n else None,'hindsight_best_side_upper_sum_eur_DIAGNOSTIC_NEVER_ENTRY_OR_STRATEGY':sum(max(x['long']['net_eur'],x['short']['net_eur']) for x in vv) if n else None,'fraction_at_least_one_positive_net_side':sum(max(x['long']['net_eur'],x['short']['net_eur'])>0 for x in vv)/n if n else None}
  return out
 return {'classification':'RETROSPECTIVE_H2_AMPLITUDE_COST_ENVELOPE;NO_DIRECTION_CHOICE;NO_PREDICTIVE_ALPHA','global':report(parts),'complete_weeks':{w:report([x for x in parts if x['iso']==w]) for w in k.weeks()}},parts

def main():
 global PHASE
 os.umask(0o077);h=os.environ['GITHUB_SHA'];a=json.loads((e.a.ROOT/(P+'ECONOMIC_COMPLETION_V1.json')).read_text());e.w.v2.runtime(h);need(a['authority']=='EXPLICIT_OWNER_SAME_CAMPAIGN_FROZEN_COHORT_COST_COMPLETION_NO_MODEL_REPLAY_20261011','AUTHORITY');need(not any(a[n] for n in ('orders','protected_forward','cloud_deployment','scientific_kernel_replay')),'SCOPE');need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-wide-economic-completion-v1.yml@refs/heads/'+e.w.old.BRANCH,'WORKFLOW');need(datetime.now(timezone.utc).isoformat()<a['expires_utc'],'EXPIRED');e.a.ancestor(a['base_head'],h);e.a.ancestor(a['design_commit'],h)
 for p,s in a['bindings'].items():need(e.w.old.filehash(p)==s,'SOURCE_BINDING')
 inv=lambda r:dict(z.split('\t',1)[::-1] for z in subprocess.check_output(['git','ls-tree','-r',r],cwd=e.a.ROOT,text=True).splitlines());old=inv(a['base_head']);new=inv(h);need(all(new.get(p)==v for p,v in old.items()),'OLD_FILES_PRESERVED');need(not e.w.v2.existing_ref(a['one_use_ref']),'CONSUMED');e.w.old.api('git/refs',{'ref':'refs/tags/'+a['one_use_ref'],'sha':h})
 with tempfile.TemporaryDirectory(prefix='mxm-wide-cost-completion-',dir=os.environ['RUNNER_TEMP']) as td:
  tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'EXISTING_OWNER_KEY')
  PHASE='AUTHENTIC_SAVED_FORECASTS_AND_EXACT_COHORT';full,pp=load_asset(key,fp,tmp,a['numeric_source']);catobj,cp=load_asset(key,fp,tmp,a['catalog_source']);qobj,qp=load_asset(key,fp,tmp,a['quote_source']);summary=full['summary'];cat=catobj['catalog'];rows=catobj['identities'];need(summary['source_head']==a['numeric_source_head'] and summary['design_commit']==a['design_commit'],'ORIGINAL_NUMERIC_SOURCE');need(summary['requests'].get('history')==900 and summary['requests'].get('tick',0)==0 and qobj['counts'].get('tick',0)==0,'PROVEN_LOCAL_CROSS_COUNTER_DEFECT_NO_PRIOR_TICK_WIRE_REPLAY')
  quotes={(int(q['symbol_id']),int(q['boundary_ms'])//1000):q for q in qobj['quotes']};required={tuple(z) for z in qobj['required']};blocked={z for z in required if all(quotes[z]['sides'].get(n,{}).get('state')=='TRANSPORT_UNRESOLVED' and quotes[z]['sides'][n].get('failure_class')=='NumericalStop' for n in ('bid','ask'))};need(len(blocked)*2<=10000 and len(full['all_economic_cohort_entries'])==257,'FROZEN_COMPLETE_COHORT_COUNT');before_sha=e.a.sha(e.a.enc(full['all_economic_cohort_entries']));col=TickOnlyCompletion();store=e.w.old.GitHubStore(h,key,e.a.ROOT/e.w.old.PUBLIC_KEY,tmp,'real');store.release=e.w.old.api('releases',{'tag_name':'mxm-wide-quote-completion-'+a['invocation_id']+'-'+os.environ['GITHUB_RUN_ID'],'target_commitish':h,'name':'MXM encrypted same frozen cohort quote completion','prerelease':True,'body':'Only previously local-counter-blocked fixed historical BID/ASK/FX windows; no scientific kernel, H1, orders or forward replay.'})
  def persist(label):return store.encrypted(e.w.old.crypto.strict_json(e.a.enc({'schema':'mxm.wide.private.quote.completion.v1','source_head':h,'numeric_source':pp,'quote_source':qp,'required':sorted(required),'quotes':[quotes[z] for z in sorted(required)],'tick_side_requests':col.counts['tick'],'original_frozen_cohort_sha256':e.a.sha(e.a.enc(qobj['quote_cohort']))})),label+'.mxmenc')
  checkpoints=[];PHASE='AUTHENTIC_FIXED_MISSING_QUOTES_ONLY'
  try:
   col.connect()
   for i,(sid,t) in enumerate(sorted(blocked,key=lambda z:(z[1],z[0]))):
    need(k.SCORE<=t<k.END,'HISTORICAL_SCOPE');quotes[sid,t]=col.quote(sid,t)
    if (i+1)%100==0:checkpoints.append(persist('quotes-'+str(i+1)));print(json.dumps({'phase':'AUTHENTIC_FROZEN_QUOTE_COMPLETION','ordinal':i+1,'new_tick_side_requests':col.counts['tick'],'scientific_kernel_calls':0,'outcomes_public':False}),flush=True)
   checkpoints.append(persist('quotes-final'))
  finally:col.close()
  PHASE='STORED_FORECAST_CURRENT_COST_EVALUATION';events=[{'sid':r['sid'],'t':r['t']-300,'h':r['h'],'iso':r['iso'],'block':r['block'],'forecast':r['forecast']} for r in full['all_economic_cohort_entries']];priced=econ.evaluate(events,rows,cat,quotes);economic=econ.report(priced);portfolio=econ.portfolio(priced);mag,magrows=magnitude_quote_envelope(qobj['quote_cohort'],rows,cat,quotes);need(before_sha==e.a.sha(e.a.enc(full['all_economic_cohort_entries'])),'STORED_FORECASTS_UNCHANGED')
  original_families_sha=e.a.sha(e.a.enc(summary['families']));correct_feature_count(summary['families']);summary['aggregate_support_rendering_correction']={'raw_feature_valid_packed_bool_count_was_calendar':'False is non-None in thin renderer; corrected to calendar minus FEATURE_GAP; raw field preserved; per-identity source counts already correct','forecast_paired_MSE_gross_increment_bootstrap_unchanged':True,'raw_families_sha256':original_families_sha};summary['original_numeric_source_head']=summary['source_head'];summary['source_head']=h;summary['economic']=slim_econ(economic);summary['portfolio']={**portfolio,'report':slim_econ(portfolio['report'])};summary['magnitude_H2_quote_envelope']=mag;summary['quote_completion']={'original_tick_requests':0,'new_tick_side_requests':col.counts['tick'],'locally_blocked_boundaries':len(blocked),'required_boundaries':len(required),'valid_fresh_complete_boundaries':sum(econ.point(quotes[z]) is not None for z in required),'side_states':dict(Counter(s.get('state') for z in required for s in quotes[z]['sides'].values())),'provider_error_codes':dict(Counter(s.get('code') for z in required for s in quotes[z]['sides'].values() if s.get('state')=='PROVIDER_ERROR')),'checkpoints':checkpoints,'release_id':store.release['id'],'scientific_kernel_calls':0,'H1_new_requests':0,'stored_forecast_cohort_sha256':before_sha,'original_frozen_collection_cohort_sha256':e.a.sha(e.a.enc(qobj['quote_cohort'])),'sources':[pp,cp,qp]};summary['requests']['tick_completed_same_frozen_cohort']=col.counts['tick'];summary['raw_scientific_result_preserved']=True
  fullout={'summary':summary,'original_numeric_source':pp,'original_unchanged_per_identity_reports':full['per_identity_reports'],'new_economic_cohort_entries':priced,'new_magnitude_H2_quote_envelope_entries':magrows,'current_native_catalog':cat,'all_current_identity_status':rows,'completed_frozen_quotes':[quotes[z] for z in sorted(required)],'previous_economic_N0_due_local_defect_retained_in_original_release':True}
  PHASE='ENCRYPTED_COMPLETED_ECONOMICS_PUBLICATION';rt.output(h,a,tmp,key,'wideeconomiccompletion',fullout,summary)
  rel={n:v for n,v in summary.items() if n not in ('quality','data_checkpoints')};rel['families']={fam:{v:x for v,x in views.items() if v!='all_classes'} for fam,views in summary['families'].items()};rel['class_global_results']={fam:{cls:{'global':z['report']['global'],'clustered':z['clustered']} for cls,z in views['all_classes'].items()} for fam,views in summary['families'].items()};rel['HARD21']['instrument_upper_bounds']={s:{n:v for n,v in z.items() if n!='quote_cohort_positions_per_complete_week'} for s,z in summary['HARD21']['instrument_upper_bounds'].items()};rel['magnitude_H2_quote_envelope']={n:v for n,v in mag.items() if n!='complete_weeks'};relay(h,a,tmp,rel)
if __name__=='__main__':
 try:main()
 except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(1)
