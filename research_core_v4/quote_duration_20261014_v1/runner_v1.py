"""Outcome-blind cost qualification, then at most one separately armed native pilot."""
import os,json,pathlib,tempfile,subprocess,math,statistics
from collections import Counter
from datetime import datetime,timezone
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.quote_path_recipient_recovery_20261013_v1 import delivery_contract_v1 as custody
from research_core_v4.cost_frequency_discovery_v1 import accounts_v1 as fx
from research_core_v4.cost_frequency_discovery_v1.kernel_v1 import entry as native_entry_cost
from competition.broker_universe_capture import entry_eligibility
from m6.cost_evidence import decode_ctrader_tick_page
from . import kernel_v1 as k
e=rt.e;P='research_core_v4/quote_duration_20261014_v1/';WF='.github/workflows/mxm-quote-duration-20261014-v1.yml';PHASE='GATE'
SCENARIOS={'S0_F0':(0.,0.),'PRIMARY_S2_F010':(2.,.10),'S5_F050':(5.,.50)}
def need(v,c):e.w.old.need(bool(v),c)
def iso(t):return datetime.fromtimestamp(t,timezone.utc).strftime('%G-W%V')
def gate():
 h=os.environ['GITHUB_SHA'];e.w.v2.runtime(h);mode='PILOT' if (e.a.ROOT/(P+'PILOT_EXECUTION_V1.json')).exists() else 'PRECHECK';a=json.loads((e.a.ROOT/(P+mode+'_EXECUTION_V1.json')).read_text())
 need(a['authority']=='EXPLICIT_OWNER_CLOUD_NATIVE_COST_FIRST_20261014' and a['mode']==mode,'OWNER_SCOPE');need(not any(a[n] for n in ('orders','protected_forward','cloud_deployment','closed_exact_replay','new_broker_requests')),'SCOPE');need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/'+WF+'@refs/heads/'+e.w.old.BRANCH,'WORKFLOW')
 need(datetime.now(timezone.utc).isoformat()<a['expires_utc'],'EXPIRED')
 for path,digest in a['bindings'].items():need(e.w.old.filehash(path)==digest,'SOURCE_BINDING')
 e.a.ancestor(a['base_head'],h);old=set(subprocess.check_output(['git','ls-tree','-r',a['base_head']],cwd=e.a.ROOT,text=True).splitlines());new=set(subprocess.check_output(['git','ls-tree','-r',h],cwd=e.a.ROOT,text=True).splitlines());need(old<=new,'OLD_FILES_CHANGED')
 public=(e.a.ROOT/(P+'RECIPIENT_PUBLIC_KEY.pem')).read_bytes();ready=json.loads((e.a.ROOT/(P+mode+'_RECIPIENT_READY_V1.json')).read_text());custody.require_ready(ready,public,a['invocation_id'],datetime.fromisoformat(a['expires_utc']));need(custody.fingerprint(public)==a['recipient_spki_sha256'],'RECIPIENT')
 need(not e.w.v2.existing_ref(a['one_use_ref']),'ONE_USE');e.w.old.api('git/refs',{'ref':'refs/tags/'+a['one_use_ref'],'sha':h});return h,a,mode,e.w.old.verify_science()

def universe(source,master,full):
 cat=source['catalog'];rows={int(r['sid']):dict(r) for r in source['identities']};light={int(r['symbolId']):r for r in cat['light']};eligible={};statuses=[];known_m5={int(r['symbol_id']) for r in master};screen=full.get('screen',{})
 for sid,q in screen.items():
  if any(int(z.get('rows',0))>0 for z in q.get('periods',[])):known_m5.add(int(sid))
 for r in full['events']:
  if r.get('prior'):known_m5.add(int(r['sid']))
 quote_ids={int(q['symbol_id']) for q in full['raw_quote_receipts']}
 for sid,r in sorted(rows.items()):
  f=cat['full'].get(str(sid));reasons=[]
  if f is None or sid not in light:reasons.append('NATIVE_CONTRACT_MISSING')
  else:
   buy,sell=entry_eligibility(light[sid],f)
   if buy is not True or sell is not True:reasons.append('NATIVE_ENTRY_DIRECTIONS_INELIGIBLE')
   fee=('commissionType','preciseTradingCommissionRate','preciseMinCommission','minCommissionType','pnlConversionFeeRate')
   if any(n not in f for n in fee):reasons.append('NATIVE_FEE_FIELDS_UNRESOLVED')
   try:
    u=int(f['minVolume']);step=int(f['stepVolume']);margin=float(r['margin_eur'])
    if not (u>0 and step>0 and u%step==0 and u<=int(f['maxVolume']) and int(f['lotSize'])>0):reasons.append('NATIVE_VOLUME_LATTICE')
    if not math.isfinite(margin) or not 0<margin<=80:reasons.append('CURRENT_MINIMUM_MARGIN_GT80_OR_UNKNOWN')
   except (KeyError,ValueError,TypeError):reasons.append('CONTRACT_VOLUME_MARGIN_MISSING')
   if not reasons:r.update(min_units=u/100,margin_eur=margin);eligible[sid]=r
  statuses.append({'sid':sid,'structural_eligible':not reasons,'structural_reasons':reasons,'known_accepted_M5':sid in known_m5,'history_state':'KNOWN_ACCEPTED_M5' if sid in known_m5 else 'OTHER_HISTORY_UNRESOLVED_NOT_ASSUMED_ABSENT','saved_quote_pages':sid in quote_ids,'quote_pages_not_contemporaneous_live_observation':True})
 need(len(rows)==5326,'BROAD_CATALOG');return cat,rows,eligible,statuses

def candidates(full,cat,rows,eligible,tmp):
 quotes={}
 for q in full['raw_quote_receipts']:
  key=(int(q['symbol_id']),int(q['boundary_ms'])//1000);need(q['boundary_ms']%1000==0 and q['boundary_ms']<1789603200000,'QUOTE_DOMAIN');need(key not in quotes or quotes[key]==q,'QUOTE_CONFLICT');quotes[key]=q
 unique={}
 for ev in full['events']:
  if ev['h']!=15:continue
  key=(int(ev['sid']),int(ev['t']));need(ev['t']+900<1789603200,'EVENT_DOMAIN');need(key not in unique or unique[key]['prior']==ev['prior'],'EVENT_CONFLICT');unique[key]=ev
 graph=fx.graph(list(rows.values()));records=[];csharp=[];summaries=[]
 for (sid,t),ev in sorted(unique.items()):
  q=quotes.get((sid,t));pages={p['side']:p for p in q.get('pages',[])} if q else {};decoded={'bid':[],'ask':[]};more=False
  for name,page in pages.items():
   need(name in ('bid','ask') and type(page['hasMore'])==bool,'PAGE_SCHEMA');more|=page['hasMore']
   zz=decode_ctrader_tick_page(page['encoded']);need(all((t-60)*1000<=z.timestamp_ms<=t*1000 for z in zz),'PAGE_TIME_WINDOW');decoded[name]=[(int(z.timestamp_ms),int(z.raw_tick)) for z in zz]
   sd=q['sides'].get(name,{})
   if sd.get('state')=='AUTHENTIC_CAUSAL_QUOTE':
    need(bool(zz),'EMPTY_CAUSAL_SIDE');last=max(zz,key=lambda z:z.timestamp_ms);need(last.timestamp_ms==sd['timestamp_ms'] and math.isclose(last.raw_tick/100000,sd['price'],abs_tol=1e-10,rel_tol=0),'DECODE_PARITY')
  feature=k.feature(decoded['bid'],decoded['ask'],t,more)
  csharp.append({'bids':decoded['bid'],'asks':decoded['ask'],'t':t,'has_more':more});summaries.append(feature)
  if sid not in eligible:en={'state':'STRUCTURAL_INELIGIBLE','eligible':False}
  elif not ev.get('prior') or ev['prior'].get('last_open',t)+300>t-1:en={'state':'CAUSAL_PRIOR_M5_UNAVAILABLE','eligible':False}
  else:
   en=native_entry_cost(ev,eligible[sid],cat['full'][str(sid)],quotes,graph,15)
   if en.get('eligible'):
    # A feasibility hurdle from the completed price range, never forecast PnL.
    scale=en['notional_eur']*ev['prior']['range_bps']/10000*math.sqrt(3)
    en['prior_15min_scale_eur']=scale;en['cost_over_prior_scale']=en['cost_eur']/scale if scale>0 else None
    if scale<=0 or en['cost_eur']>scale:en.update(eligible=False,state='COST_EXCEEDS_CAUSAL_PRIOR_SCALE')
  records.append({'sid':sid,'t':t,'iso':iso(t),'feature':feature,'entry':en})
 # Both native kernel and Python get only causal raw price/time arrays, not outcomes.
 infile=tmp/'causal-input.jsonl';outfile=tmp/'csharp-output.jsonl';infile.write_text(''.join(json.dumps(z)+'\n' for z in csharp))
 subprocess.run(['dotnet',str(e.a.ROOT/(P+'csharp/bin/Release/net8.0/Replay.dll')),str(infile),str(outfile)],check=True,stdout=subprocess.DEVNULL)
 results=[json.loads(z) for z in outfile.read_text().splitlines()];need(len(results)==len(summaries),'CSHARP_ROW_COUNT')
 for python,cs in zip(summaries,results):
  need(set(python)==set(cs),'CSHARP_FIELDS')
  for name,v in python.items():need(math.isclose(v,cs[name],rel_tol=1e-12,abs_tol=1e-12) if type(v)==float else v==cs[name],'CSHARP_PARITY')
 return records,quotes,graph,{'authentic_causal_rows':len(results),'feature_parity':'PASS','native_automate_adapter_compile':'PASS','Cloud_feed_history_delivery_equivalence':'UNPROVEN_NO_DEPLOYMENT;ONLY_NATIVE_FIELD_AND_KERNEL_COMPATIBILITY_VERIFIED'}

def quote_reason(q):
 if q is None:return 'SAVED_QUOTE_NOT_PRESENT'
 s=q['sides']
 if any(s.get(n,{}).get('source_has_more',True) for n in ('bid','ask')):return 'QUOTE_PAGE_INCOMPLETE_OR_UNRESOLVED'
 if any(s.get(n,{}).get('state')!='AUTHENTIC_CAUSAL_QUOTE' for n in ('bid','ask')):return 'NO_CAUSAL_QUOTE_STATE'
 if any(s[n].get('age_ms',10**9)>5000 for n in ('bid','ask')):return 'QUOTE_AGE_GT5S'
 if abs(s['bid']['timestamp_ms']-s['ask']['timestamp_ms'])>2000:return 'SIDE_SKEW_GT2S'
 return 'SUPPORTED_QUOTE' if fx.point(q) else 'CROSSED_OR_NONPOSITIVE_QUOTE'

def complete_support(ev,row,f,quotes,graph):
 for t in (ev['t'],ev['t']+900):
  why=quote_reason(quotes.get((row['sid'],t)))
  if why!='SUPPORTED_QUOTE':return ('ENTRY_' if t==ev['t'] else 'EXIT_')+why
  currencies=fx.currencies(row,f)|{row['quote']}
  for ccy in currencies:
   path=fx.route(ccy,'EUR',graph)
   if path is None:return 'FX_ROUTE_UNAVAILABLE'
   if any(fx.point(quotes.get((sid,t))) is None for sid,forward in path):return 'NATIVE_FX_QUOTE_UNAVAILABLE'
  for name in ('bid','ask'):
   if fx.commission(row,f,row['min_units'],fx.point(quotes[(row['sid'],t)])[name],t,quotes,graph) is None:return 'COMMISSION_OR_FX_UNAVAILABLE'
 return 'COMPLETE_NATIVE_QUOTES_CURRENT_TERMS'

def qualification(records,rows,eligible,cat,statuses,quotes,graph,parity,full):
 support=Counter();paired=[];feasible=[];costs=[]
 for ev in records:
  if 'cost_eur' in ev['entry']:costs.append(ev['entry']['cost_eur'])
  if ev['sid'] not in eligible:support['STRUCTURAL_INELIGIBLE']+=1;continue
  why=complete_support(ev,eligible[ev['sid']],cat['full'][str(ev['sid'])],quotes,graph);support[why]+=1
  # Exit availability is a descriptive denominator only, never an entry filter.
  if ev['entry'].get('eligible') and ev['feature'].get('state')=='SUPPORTED' and ev['feature']['model_side']:
   feasible.append(ev)
   if why=='COMPLETE_NATIVE_QUOTES_CURRENT_TERMS':paired.append(ev)
 weeks=sorted({r['iso'] for r in paired});half=sorted(full['summary']['weeks']);mid=len(half)//2
 gate=len(paired)>=32 and len(weeks)>=8 and any(r['iso'] in half[:mid] for r in paired) and any(r['iso'] in half[mid:] for r in paired)
 return {'schema':'mxm.quote.duration.cost.qualification.v1','catalog_total':len(rows),'catalog_archived_separate':len(cat.get('archived',[])),'structural_eligible_current':len(eligible),'structural_reasons':dict(Counter(x for z in statuses for x in z['structural_reasons'])),'known_M5_identity_count':sum(z['known_accepted_M5'] for z in statuses),'identities_with_saved_quote_pages':sum(z['saved_quote_pages'] for z in statuses),'identities_without_saved_quote_pages':sum(not z['saved_quote_pages'] for z in statuses),'research_catalog_not_capped':True,'saved_candidate_boundaries':len(records),'saved_candidate_identities':len({r['sid'] for r in records}),'feature_states':dict(Counter(z['feature']['state'] for z in records)),'entry_reasons':dict(Counter(z['entry']['state'] for z in records)),'native_quote_support_reasons':dict(support),'native_complete_feature_and_cost_feasible':len(paired),'entry_feasible_before_exit_availability':len(feasible),'supported_complete_ISO_weeks':weeks,'complete_native_cost_pair_count_is_not_fills':True,'entry_cost_distribution_eur':{'N':len(costs),'min':min(costs) if costs else None,'median':statistics.median(costs) if costs else None,'max':max(costs) if costs else None},'native_CSharp':parity,'temporal_support_gate_pass':gate,'gate_scope':'MIN32_PAIRED_FEATURE_COST_EVENTS_MIN8_WEEKS_BOTH_HALVES_FEASIBILITY_ONLY_NOT_POWER','pilot_qualified':gate,'returns_or_NET_examined':False,'new_broker_requests':0,'orders':0,'HARD21':False,'missing_quotes_not_broker_inability':True,'statuses':statuses,'per_identity_support':{str(s):{'boundaries':sum(r['sid']==s for r in records),'feasible_before_exit':sum(r['sid']==s for r in feasible),'native_complete_feature_cost':sum(r['sid']==s for r in paired)} for s in sorted({r['sid'] for r in records})}}

def account(ev,d,row,f,quotes,graph,slip=2.,fund=.10):
 if d==0:return {'midpoint_gross_eur':0.,'spread_drag_eur':0.,'slippage_drag_eur':0.,'gross_eur':0.,'entry_commission_eur':0.,'exit_commission_eur':0.,'pnl_conversion_fee_eur':0.,'funding_stress_eur':0.,'net_eur':0.,'cash_tie':True}
 z=fx.account(d,row,f,ev['t'],ev['t']+900,.25,quotes,graph,slip,fund,False)
 if z is None:return None
 q0=fx.point(quotes.get((row['sid'],ev['t'])));q1=fx.point(quotes.get((row['sid'],ev['t']+900)));u=row['min_units'];p0=q0['ask'] if d>0 else q0['bid'];p1=q1['bid'] if d>0 else q1['ask'];mid=fx.convert(d*u*(q1['mid']-q0['mid']),row['quote'],'EUR',ev['t']+900,quotes,graph);gross=fx.convert(d*u*(p1-p0),row['quote'],'EUR',ev['t']+900,quotes,graph);need(mid is not None and gross is not None,'NATIVE_DECOMPOSITION')
 z.update(midpoint_gross_eur=mid,spread_drag_eur=mid-gross,slippage_drag_eur=gross-z['gross_eur']);return z

def aggregate(records,scenario='PRIMARY_S2_F010'):
 usable=[r for r in records if r.get('accounts',{}).get(scenario) is not None];fields=('midpoint_gross_eur','spread_drag_eur','slippage_drag_eur','gross_eur','entry_commission_eur','exit_commission_eur','pnl_conversion_fee_eur','funding_stress_eur','net_eur');out={'proposed':len(records),'paired_evaluable':len(usable),'censored':len(records)-len(usable)}
 for name in ('model','count','momentum'):out[name]={n:sum(r['accounts'][scenario][name][n] for r in usable) if usable else None for n in fields}
 for name in ('count','momentum'):out[name+'_paired_increment_eur']=sum(r['accounts'][scenario]['model']['net_eur']-r['accounts'][scenario][name]['net_eur'] for r in usable) if usable else None
 out['cash']={'net_eur':0.,'positions':0};return out

def pilot(records,eligible,cat,quotes,graph,full,q):
 selected=[]
 for ev in records:
  if not (ev['entry'].get('eligible') and ev['feature'].get('state')=='SUPPORTED' and ev['feature']['model_side']):continue
  row=eligible[ev['sid']];f=cat['full'][str(ev['sid'])];accounts={}
  for sc,(slip,fund) in SCENARIOS.items():
   values={n:account(ev,ev['feature'][field],row,f,quotes,graph,slip,fund) for n,field in [('model','model_side'),('count','count_side'),('momentum','momentum_side')]};accounts[sc]=values if all(v is not None for v in values.values()) else None
  selected.append({**ev,'accounts':accounts})
 def value(ev,d):return account(ev,d,eligible[ev['sid']],cat['full'][str(ev['sid'])],quotes,graph)
 portfolio=k.ledger(records,value);keys={(z['sid'],z['t']) for z in portfolio['selected']};ledger_records=[z for z in selected if (z['sid'],z['t']) in keys];weeks=sorted(full['summary']['weeks']);blocks=[weeks[i:i+10] for i in range(0,len(weeks),10)]
 result={'schema':'mxm.quote.duration.native.pilot.summary.v1','mechanism':'DIRECTIONAL_QUOTE_WAITING_TIME_ASYMMETRY_V1','qualification':{n:v for n,v in q.items() if n not in ('statuses','per_identity_support')},'scenarios':{sc:aggregate(selected,sc) for sc in SCENARIOS},'weekly':{w:aggregate([r for r in selected if r['iso']==w]) for w in weeks},'blocks':[aggregate([r for r in selected if r['iso'] in b]) for b in blocks],'halves':[aggregate([r for r in selected if r['iso'] in b]) for b in (weeks[:len(weeks)//2],weeks[len(weeks)//2:])],'portfolio':portfolio,'portfolio_accounting':aggregate(ledger_records),'portfolio_weekly_closed':dict(Counter(iso(r['t']) for r in portfolio['closed'])),'minimum_ticket_risk_reference_breaches':sum(r['accounts']['PRIMARY_S2_F010'] is not None and -r['accounts']['PRIMARY_S2_F010']['model']['net_eur']>r['entry']['risk_eur'] for r in selected),'NET_full_historical_actual':None,'historical_charges_slippage_fills':'UNRESOLVED_NOT_ZERO;CURRENT_NATIVE_TERMS_PLUS_FROZEN_STRESS','native_quote_reference_NET_vs_proxy':'BIDASK_AND_FX_AUTHENTIC_WHEN_COMPLETE;FEES_CURRENT_SLIPPAGE_FUNDING_PROXY_NO_ACTUAL_FILLS','HARD21':False,'orders':0,'fills':0,'protected_forward':False,'cloud_deployment':False,'new_broker_requests':0,'old_predictor_calls':0,'alpha_certified':False,'inference':'DESCRIPTIVE_PRIOR_ADAPTIVE_EXPOSURE_DEPENDENT_CALENDAR_CROSS_SYMBOL_NO_INDEPENDENT_SIGNIFICANCE_OR_GLOBAL_FAMILY_CLOSURE'}
 primary=result['scenarios']['PRIMARY_S2_F010'];result['verdict']='CLOSED_NO_PROMOTION_NEGATIVE_EXACT' if primary['paired_evaluable'] and (primary['model']['net_eur']<=0 or primary['count_paired_increment_eur']<=0 or primary['momentum_paired_increment_eur']<=0) else 'EXPLORATORY_ONLY_NO_CERTIFICATION' if primary['paired_evaluable'] else 'DATA_LIMITED_NO_NET_RESULT';return {'summary':result,'records':records,'proposed_records':selected,'identity_status':q['statuses'],'identity_support':q['per_identity_support']},result

def publish(head,a,mode,tmp,key,value,summary):
 from research_core_v4.numeric_development_v1.public_output_guard_v1 import validate_public_blob,ROOT as PUB
 kind='duration-'+mode.lower();path=PUB+'OWNER_DURATION_'+mode+'_V1.json';status={'schema':e.w.SCHEMA,'source_head':head,'phase':'PUBLICATION','status':'NOT_PERSISTED','failure_code':'NONE','run_id':int(os.environ['GITHUB_RUN_ID'])}
 store=e.w.old.GitHubStore(head,key,e.a.ROOT/e.w.old.PUBLIC_KEY,tmp,'real');store.release=e.w.old.api('releases',{'tag_name':'mxm-duration-'+a['invocation_id']+'-'+os.environ['GITHUB_RUN_ID'],'target_commitish':head,'name':'MXM encrypted native duration '+mode,'prerelease':True,'body':validate_public_blob(path,status).decode()})
 value=e.w.old.crypto.strict_json(e.a.enc(value));primary=store.encrypted(value,kind+'-owner-result.mxmenc');loaded,proof=load_asset(key,e.w.old.FP,tmp,{'release_id':store.release['id'],'asset_id':primary['id'],'ciphertext_sha256':primary['ciphertext_sha256']});need(loaded==value,'OWNER_READBACK_PARITY');summary=e.w.old.crypto.strict_json(e.a.enc(summary));summary.update(source_head=head,run_id=int(os.environ['GITHUB_RUN_ID']));envelope={'schema':'mxm.duration.verified.summary.v1','summary':summary,'summary_canonical_sha256':e.a.sha(e.a.enc(summary)),'original_primary':proof,'source_head':head,'source_run':int(os.environ['GITHUB_RUN_ID']),'recipient_spki_sha256':a['recipient_spki_sha256'],'OWNER_READBACK_SUCCESS':True,'NUMERIC_SUCCESS':mode=='PILOT','QUALIFICATION_SUCCESS':mode=='PRECHECK','DELIVERY_SUCCESS':False,'mode':mode}
 relay=e.upload_extra(store.release,tmp,e.a.ROOT/(P+'RECIPIENT_PUBLIC_KEY.pem'),envelope,kind+'-recipient-summary.mxmenc');store.encrypted({'primary':proof,'relay':relay,'summary_sha256':envelope['summary_canonical_sha256'],'resources':e.w.old.usage()},kind+'-attestation.mxmenc');status.update(phase='FINAL',status='PASS',encrypted_artifact_name=relay['name'],encrypted_artifact_sha256=relay['ciphertext_sha256']);body=validate_public_blob(path,status);e.w.old.api('releases/'+str(store.release['id']),{'body':body.decode()},method='PATCH');need(e.w.old.api('releases/'+str(store.release['id']))['body'].encode()==body,'PUBLIC_READBACK');print(body.decode().strip(),flush=True)

def main():
 global PHASE
 os.umask(0o077);head,a,mode,(master,entries,digits,manifest)=gate()
 with tempfile.TemporaryDirectory(prefix='mxm-duration-',dir=os.environ['RUNNER_TEMP']) as directory:
  tmp=pathlib.Path(directory);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'OWNER_KEY');PHASE='ACCEPTED_INPUT_RECOVERY';full,sourceproof=load_asset(key,fp,tmp,a['quote_source']);source,catproof=load_asset(key,fp,tmp,a['catalog_source']);need(full['summary']['source_head']==a['quote_source']['head_sha'],'ORIGINAL_SOURCE_HEAD');cat,rows,eligible,statuses=universe(source,master,full);PHASE='CAUSAL_COST_NATIVE_CSHARP';records,quotes,graph,parity=candidates(full,cat,rows,eligible,tmp);q=qualification(records,rows,eligible,cat,statuses,quotes,graph,parity,full);q.update(source_provenance=sourceproof,catalog_provenance=catproof)
  if mode=='PRECHECK':value={'summary':q,'records_without_outcomes':records};summary={n:v for n,v in q.items() if n not in ('statuses','per_identity_support')}
  else:
   prior,priorproof=load_asset(key,fp,tmp,a['qualification_source']);need(prior['summary']['pilot_qualified'] is True and q['pilot_qualified'] is True,'PREPILOT_QUALIFICATION');need(e.a.sha(e.a.enc(records))==e.a.sha(e.a.enc(prior['records_without_outcomes'])),'PREFLIGHT_COHORT_CHANGE');PHASE='ONE_NEW_PILOT';value,summary=pilot(records,eligible,cat,quotes,graph,full,q);summary['qualification_source']=priorproof
  summary['scientific_design_sha256']=e.w.old.filehash(P+'DESIGN_V1.json');summary['mechanism_reconciliation_sha256']=e.w.old.filehash(P+'RECONCILIATION_V1.json');PHASE='ENCRYPTED_PUBLICATION';publish(head,a,mode,tmp,key,value,summary)
if __name__=='__main__':
 try:main()
 except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(1)
