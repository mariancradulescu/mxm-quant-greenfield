"""Complete friction bridge on conserved quotes only. No broker requests/predictor."""
import os,json,pathlib,tempfile,base64,math,statistics
from datetime import datetime,timezone
from collections import Counter,defaultdict
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.cost_frequency_discovery_v1 import accounts_v1 as fx
from research_core_v4.native_coverage_expansion_20261014_v1.runner_v1 import distribution,reference
from research_core_v4.quote_path_recipient_recovery_20261013_v1 import delivery_contract_v1 as custody
E=rt.e;P='research_core_v4/native_coverage_economic_completion_20261014_v1/';WF='.github/workflows/mxm-native-coverage-economic-completion-20261014-v1.yml'
def need(v,c):E.w.old.need(bool(v),c)
def primary_cost(ref,rate):
 if 'break_even_eur' not in ref:return ref
 out=dict(ref);need(0<=rate<1,'PNL_FEE_RATE')
 fees=ref['commission_RT_eur']+ref['funding_stress_eur'];increment=fees/(1-rate)-fees
 out.update(pnl_conversion_fee_rate=rate,break_even_conversion_fee_eur=increment,break_even_eur=ref['break_even_eur']+increment,break_even_bps=(ref['break_even_eur']+increment)/ref['notional_eur']*10000,planned_risk_eur=ref['planned_risk_eur']+increment,eligible=ref['eligible'] and ref['planned_risk_eur']+increment<=2,pnl_conversion_fee_scope='CURRENT_RATE_ON_POSITIVE_EXECUTABLE_GROSS;REFERENCE_EXIT_FEES_USE_ENTRY_QUOTES;NOT_ACTUAL_FILL')
 if ref['eligible'] and not out['eligible']:out['state']='REFERENCE_RISK_INFEASIBLE_AFTER_PNL_FEE'
 return out

def main():
 os.umask(0o077);a=json.loads((E.a.ROOT/(P+'EXECUTION_V1.json')).read_text());head=os.environ['GITHUB_SHA'];E.w.v2.runtime(head);E.a.ancestor(a['base_head'],head)
 need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_RUN_ATTEMPT']=='1' and os.environ['GITHUB_WORKFLOW_REF']==E.w.old.REPO+'/'+WF+'@refs/heads/'+E.w.old.BRANCH,'WORKFLOW_SCOPE')
 need(a['authority']=='EXPLICIT_OWNER_COMPLETE_NATIVE_ECONOMIC_ACCOUNTING_20261014' and datetime.now(timezone.utc).isoformat()<a['expires_utc'],'OWNER_SCOPE')
 for path,hash in a['bindings'].items():need(E.w.old.filehash(path)==hash,'SOURCE_BINDING')
 pub=(E.a.ROOT/a['recipient_public_path']).read_bytes();ready=json.loads((E.a.ROOT/(P+'RECIPIENT_READY_V1.json')).read_text());custody.require_ready(ready,pub,a['invocation_id'],datetime.fromisoformat(a['expires_utc']));need(custody.fingerprint(pub)==a['recipient_spki_sha256'],'RECIPIENT')
 need(not E.w.v2.existing_ref(a['one_use_ref']),'CONSUMED');E.w.old.api('git/refs',{'ref':'refs/tags/'+a['one_use_ref'],'sha':head})
 with tempfile.TemporaryDirectory(prefix='mxm-economic-complete-',dir=os.environ['RUNNER_TEMP']) as td:
  tmp=pathlib.Path(td);key,fp=E.w.old._private_key_from_secret(tmp);need(fp==E.w.old.FP,'OWNER_KEY')
  result,proof=load_asset(key,fp,tmp,a['primary']);summary=result['summary'];source,_=load_asset(key,fp,tmp,a['catalog_source']);rows={int(r['sid']):r for r in source['identities']};cat=source['catalog'];g=fx.graph(list(rows.values()));quotes={}
  for checkpoint in result['checkpoints']:
   if checkpoint['name']=='prospective-plan.mxmenc':continue
   obj,_=load_asset(key,fp,tmp,{'release_id':a['primary']['release_id'],'asset_id':checkpoint['id'],'ciphertext_sha256':checkpoint['ciphertext_sha256']})
   for q in obj.get('quotes',[]):quotes[int(q['symbol_id']),int(q['boundary_ms'])//1000]=q
  new_keys=set(quotes)
  # Restore existing quote-bearing sources too, so reused windows stay authentic.
  for binding in result['archive_proofs']:
   obj,_=load_asset(key,fp,tmp,binding)
   for q in obj.get('new_quotes',[])+obj.get('quotes',[])+obj.get('raw_quote_receipts',[]):
    k=(int(q['symbol_id']),int(q['boundary_ms'])//1000)
    if k not in quotes:quotes[k]=q
  new_windows=[]
  for sid,t in sorted(new_keys):
   q=quotes[sid,t];pages={p['side']:p for p in q.get('pages',[])};new_windows.append({'sid':sid,'window_from_utc':datetime.fromtimestamp(t-60,timezone.utc).isoformat(),'window_to_utc':datetime.fromtimestamp(t,timezone.utc).isoformat(),'pages_saved':len(pages),'bid_rows':len(pages.get('bid',{}).get('encoded',[])),'ask_rows':len(pages.get('ask',{}).get('encoded',[])),'bid_has_more':pages.get('bid',{}).get('hasMore'),'ask_has_more':pages.get('ask',{}).get('hasMore'),'bilateral_nonempty':all(bool(pages.get(side,{}).get('encoded')) for side in ('bid','ask')),'fresh_complete':fx.point(q) is not None,'side_states':{side:q['sides'].get(side,{}).get('state') for side in ('bid','ask')}})
  records=[];rates=[]
  for ev in result['records']:
   row=rows[ev['sid']];f=cat['full'][str(ev['sid'])];rate=int(f['pnlConversionFeeRate'])/10000 if row['quote']!='EUR' else 0.;rates.append(rate);refs={str(s):primary_cost(reference(row,f,ev['t'],quotes,g,s),rate) for s in (0,2,5)};bridge={}
   q0=fx.point(quotes.get((row['sid'],ev['t'])));q1=fx.point(quotes.get((row['sid'],ev['t']+900)))
   for slip in (0,2,5):
    values=[]
    for d in (1,-1):
     z=fx.account(d,row,f,ev['t'],ev['t']+900,.25,quotes,g,slip,.10) if q0 and q1 else None
     if z is not None:
      units=row['min_units'];mid=fx.convert(d*units*(q1['mid']-q0['mid']),row['quote'],'EUR',ev['t']+900,quotes,g);native=fx.convert(d*units*((q1['bid'] if d>0 else q1['ask'])-(q0['ask'] if d>0 else q0['bid'])),row['quote'],'EUR',ev['t']+900,quotes,g)
      need(mid is not None and native is not None,'FX_PARITY');z.update(midpoint_gross_eur=mid,spread_drag_eur=mid-native,slippage_drag_eur=native-z['gross_eur']);z['total_cost_eur']=sum(z[k] for k in ('spread_drag_eur','slippage_drag_eur','entry_commission_eur','exit_commission_eur','pnl_conversion_fee_eur','funding_stress_eur'));notional=fx.convert(-units*q0['mid'],row['quote'],'EUR',ev['t'],quotes,g);z['total_cost_bps_entry_notional']=z['total_cost_eur']/(-notional)*10000 if notional is not None and notional<0 else None;need(math.isclose(mid-z['total_cost_eur'],z['net_eur'],abs_tol=1e-8,rel_tol=1e-8),'COST_BRIDGE')
     values.append(z)
    bridge[str(slip)]={'long':values[0],'short':values[1]}
   records.append({**ev,'reference':refs,'two_direction_accounting':bridge,'side_payoffs_scope':'DESCRIPTIVE_ACCOUNTING_NO_TRADING_MODEL;NOT_SELECTED_BY_SIDE_RETURN'})
  def stats(rr):
   known=[r['reference']['2'] for r in rr if 'break_even_eur' in r['reference']['2']];paired=[r for r in rr if all(r['two_direction_accounting']['2'][d] is not None for d in ('long','short'))]
   out={'opportunities':len(rr),'entry_cost_known':len(known),'entry_reference_feasible':sum(r['reference']['2']['eligible'] for r in rr),'paired_actual_entry_exit_reference':len(paired),'break_even_eur':distribution([r['break_even_eur'] for r in known]),'break_even_bps':distribution([r['break_even_bps'] for r in known]),'planned_risk_eur':distribution([r['planned_risk_eur'] for r in known]),'entry_cost_states':dict(Counter(r['reference']['2']['state'] for r in rr))}
   for side in ('long','short'):
    out[side+'_paired_costs']={k:distribution([r['two_direction_accounting']['2'][side][k] for r in paired]) for k in ('spread_drag_eur','slippage_drag_eur','entry_commission_eur','exit_commission_eur','pnl_conversion_fee_eur','funding_stress_eur','total_cost_eur','total_cost_bps_entry_notional')}
   return out
  dims={}
  for dim in ('sid','class','quote','session_hour','iso'):
   groups=defaultdict(list)
   for r in records:groups[str(r[dim])].append(r)
   dims[dim]={k:stats(v) for k,v in groups.items()}
  weekly={}
  for w,v in summary['consecutive_week_reference_capacity'].items():
   rr=[r for r in records if r['phase']=='CONSECUTIVE' and r['iso']==w];active=[];accepted=[];why=Counter()
   for ev in sorted(rr,key=lambda z:(z['t'],z['sid'])):
    active=[x for x in active if x['exit']>ev['t']];ref=ev['reference']['2']
    if not ref['eligible']:why['ENTRY_REFERENCE_NOT_FEASIBLE_OR_NA']+=1;continue
    if any(x['sid']==ev['sid'] for x in active):why['SAME_SYMBOL']+=1;continue
    if sum(x['risk'] for x in active)+ref['planned_risk_eur']>2:why['AGGREGATE_RISK']+=1;continue
    if sum(x['margin'] for x in active)+ref['margin_eur_current']>80:why['AGGREGATE_MARGIN']+=1;continue
    active.append({'exit':ev['t']+900,'sid':ev['sid'],'risk':ref['planned_risk_eur'],'margin':ref['margin_eur_current']});accepted.append(ev)
   weekly[w]={**v,'entry_reference_allocatable':len(accepted),'entry_exit_accounting_supported':sum(all(ev['two_direction_accounting']['2'][s] is not None for s in ('long','short')) for ev in accepted),'collision_reasons':dict(why),'PNL_fee_included':True}
  final={**summary,'schema':'mxm.native.coverage.completed.economic.summary.v1','original_coverage_head':summary['source_head'],'economic_completion_head':head,'economic_completion_run':int(os.environ['GITHUB_RUN_ID']),'new_quote_windows':new_windows,'new_fresh_eligible_baseline_uncovered':len({w['sid'] for w in new_windows if w['fresh_complete']} & {r['sid'] for r in summary['selected_identities']}),'new_bilateral_eligible_identity_ids':sorted({w['sid'] for w in new_windows if w['bilateral_nonempty']} & {r['sid'] for r in summary['selected_identities']}),'PNL_conversion_fee_included_in_break_even':True,'PNL_fee_rates':distribution(rates),'economics':stats(records),'per_dimension':dims,'consecutive_week_reference_capacity':weekly,'no_new_broker_requests':True,'gross_cost_NET_model':None,'paired_comparators':None,'original_costs_superseded_for_missing_PNL_fee_only':True,'causal_candidate_review':{'native_shared_observables':'BID_ASK_PRICE_TIME_AND_CURRENT_SYMBOL_CONTRACT;ACTUAL_CLOUD_PARITY_NOT_CERTIFIED','new_coverage_improves':'ECONOMIC_SUPPORT_AND_COST_DISTRIBUTION;NOT_DIRECTION_CAUSALITY','closed_families_not_replayed':['DIRECTIONAL_QUOTE_WAITING_TIME_ASYMMETRY_V1','NATIVE_NET_SIDE_COST_CONDITIONING_V1','NATIVE_COST_TAIL_ABSTENTION_V1'],'new_candidate_considered':'SESSION_REOPEN_INVENTORY_REPRICING_FROM_NATIVE_PRICE_AND_SPREAD','economic_rationale':'Predictable native session boundaries may concentrate adjustment of dealer inventory quotes; a distinct causal mechanism would require preopen-to-postopen time-aligned state and a frozen cost-matched comparator.','qualified':False,'infirmation_design_not_armed':'Require incremental paired NET versus session-only and cost-only comparators with causal entry selection; no post-hoc direction/threshold rescue.','specific_missing_support':'Acquired fixed 60s clock windows do not continuously cover actual per-symbol session reopening and adjacent preopen/postopen state. Sparse grid and incomplete fresh entry/exit quotes do not establish per-week causal opportunity count.','decision':'NO_PILOT_NO_DIRECTIONAL_NET_CLAIM;NEXT_TRANCHE_REQUIRES_PROSPECTIVE_SESSION_ALIGNED_HISTORY_DESIGN'}}
  store=E.w.old.GitHubStore(head,key,E.a.ROOT/E.w.old.PUBLIC_KEY,tmp,'real');store.release=E.w.old.api('releases',{'tag_name':'mxm-native-economic-completion-'+os.environ['GITHUB_RUN_ID'],'target_commitish':head,'name':'MXM encrypted complete native friction bridge','prerelease':True,'body':'Existing authenticated quotes only. No data recollection, predictive pilot or orders.'})
  full=store.encrypted({'summary':final,'records':records,'original_primary_proof':proof},'complete-economic-result.mxmenc');final['complete_primary']={**full,'release_id':store.release['id']};relay=E.upload_extra(store.release,tmp,E.a.ROOT/a['recipient_public_path'],final,'complete-recipient-summary.mxmenc')
  safe={'schema':final['schema'],'source_head':head,'run_id':int(os.environ['GITHUB_RUN_ID']),'OWNER_READBACK_SUCCESS':True,'DELIVERY_SUCCESS':False,'release_id':store.release['id'],'primary':full,'relay':relay,'no_new_broker_requests':True,'PNL_conversion_fee_included_in_break_even':True,'pilot_executed':False,'HARD21':False}
  E.w.old.api('releases/'+str(store.release['id']),{'body':json.dumps(safe,sort_keys=True)},method='PATCH')
  cipher=E.w.old.download(next(x for x in E.w.old.api('releases/'+str(store.release['id'])+'/assets') if x['id']==relay['id'])['browser_download_url'],relay['size']);need(E.a.sha(cipher)==relay['ciphertext_sha256'],'RELAY_SHA');entries=[]
  for path,content in [(P+'RECIPIENT_SUMMARY_V1.mxmenc.b64',base64.b64encode(cipher).decode()+'\n'),(P+'RESULT_PUBLIC_SAFE_V1.json',json.dumps(safe,sort_keys=True,indent=2)+'\n')]:
   blob=E.w.old.api('git/blobs',{'content':content,'encoding':'utf-8'});entries.append({'path':path,'mode':'100644','type':'blob','sha':blob['sha']})
  need(E.w.old.api('git/ref/heads/'+E.w.old.BRANCH)['object']['sha']==head,'LIVE_HEAD');tree=E.w.old.api('git/trees',{'base_tree':E.w.old.api('git/commits/'+head)['tree']['sha'],'tree':entries});commit=E.w.old.api('git/commits',{'message':'Preserve verified encrypted native economic cost bridge [skip ci]','parents':[head],'tree':tree['sha']});E.w.old.api('git/refs/heads/'+E.w.old.BRANCH,{'sha':commit['sha'],'force':False},method='PATCH');print(json.dumps(safe,sort_keys=True),flush=True)
if __name__=='__main__':
 try:main()
 except Exception as ex:
  print('FAIL_CLOSED_NATIVE_ECONOMIC_COMPLETION_'+type(ex).__name__,flush=True);raise SystemExit(1) from None
