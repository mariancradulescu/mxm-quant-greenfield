"""Single bounded broad discovery, authentic staged collection and numeric evaluation."""
import os,json,pathlib,tempfile,subprocess,base64,math
from collections import Counter,defaultdict
from datetime import datetime,timezone
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.executable_coverage_diagnostic_v1.runner_v1 import relay
from research_core_v4.wide_greenfield_v1 import kernel_v1 as k,economics_v1 as econ,collect_v1 as c
e=rt.e;P='research_core_v4/wide_greenfield_v1/';PHASE='GATE'
def need(x,code):e.w.old.need(bool(x),code)
def inventory(ref):return dict(z.split('\t',1)[::-1] for z in subprocess.check_output(['git','ls-tree','-r',ref],cwd=e.a.ROOT,text=True).splitlines())
def hsupport(bars):return {'rows':len(bars),'first_utc':datetime.fromtimestamp(min(bars),timezone.utc).isoformat() if bars else None,'last_utc':datetime.fromtimestamp(max(bars),timezone.utc).isoformat() if bars else None,'24x7_missing_not_all_provider_losses':(k.END-k.START)//3600-len(bars)}
def thin(rows):return [{n:r[n] for n in ('sid','t','h','family','forecast','y','iso','block','class')}|{'feature':bool(r['feature'])} for r in rows]
def slim_econ(report):
 ww={}
 for w,r in report['complete_weeks'].items():
  a=r['groups']['ALL_CALCULABLE'];b=r['groups']['ELIGIBLE'];v=b['scenarios']['S2_F010_DAY'];ww[w]=[r['cohort'],a['entries'],a['evaluable_model'],b['entries'],b['evaluable_model'],b['exit_censored'],v['model_net_eur'],v['paired_baseline_net_eur']]
 return {'global':report['global'],'blocks':report['blocks'],'week_columns':['cohort','calculable','calculable_priced','eligible','eligible_priced','eligible_censored','NET_S2_F010_DAY_eur','paired_baseline_eur'],'complete_weeks':ww}
def gate():
 h=os.environ['GITHUB_SHA'];a=json.loads((e.a.ROOT/(P+'EXECUTION_V1.json')).read_text());e.w.v2.runtime(h);need(a['authority']=='EXPLICIT_OWNER_WIDE_GREENFIELD_STAGED_AUTHENTIC_RESEARCH_20261011' and not any(a[n] for n in ('orders','protected_forward','cloud_deployment','closed_exact_replay')),'AUTHORITY')
 need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-wide-greenfield-v1.yml@refs/heads/'+e.w.old.BRANCH,'WORKFLOW');need(datetime.now(timezone.utc).isoformat()<a['expires_utc'],'EXPIRED');e.a.ancestor(a['base_head'],h);e.a.ancestor(a['design_commit'],h)
 for p,s in a['bindings'].items():need(e.w.old.filehash(p)==s,'SOURCE_BINDING')
 old=inventory(a['base_head']);new=inventory(h);need(all(new.get(p)==v for p,v in old.items()),'ALL_OLD_FILES_PRESERVED');e.w.old.verify_science();need(not e.w.v2.existing_ref(a['one_use_ref']),'CONSUMED');e.w.old.api('git/refs',{'ref':'refs/tags/'+a['one_use_ref'],'sha':h});return h,a

def main():
 global PHASE
 os.umask(0o077);h,a=gate()
 with tempfile.TemporaryDirectory(prefix='mxm-wide-greenfield-',dir=os.environ['RUNNER_TEMP']) as td:
  tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'EXISTING_OWNER_KEY');oldhist,hp=load_asset(key,fp,tmp,a['native_history_source']);oldfull,qp=load_asset(key,fp,tmp,a['fullcost_source']);oldv1,vp=load_asset(key,fp,tmp,a['qualification_source']);need(oldv1['summary']['decision']=='DATA_LIMITED','V1_PRESERVED')
  quotes={(int(q['symbol_id']),int(q['boundary_ms'])//1000):q for q in oldfull['private_boundary_receipts']};quotes.update({(int(q['symbol_id']),int(q['boundary_ms'])//1000):q for q in oldv1['private_quote_receipts']});existing_quote_keys=set(quotes);del oldv1,oldfull
  native={int(s):{int(t):z for t,z in zz.items()} for s,zz in oldhist['bars'].items()};native={s:c.aggregate_m5(zz) for s,zz in native.items()};del oldhist
  primarymanifest=json.loads((e.a.ROOT/'research_core_v3/state/PRIMARY_145_INPUT_MANIFEST_V1.json').read_text());primary_ids={int(x['symbol_id']) for x in primarymanifest['primary_series']};col=c.Collector();store=e.w.old.GitHubStore(h,key,e.a.ROOT/e.w.old.PUBLIC_KEY,tmp,'real');store.release=e.w.old.api('releases',{'tag_name':'mxm-wide-greenfield-history-'+a['invocation_id']+'-'+os.environ['GITHUB_RUN_ID'],'target_commitish':h,'name':'MXM encrypted broad catalog and staged historical collection','prerelease':True,'body':'Authentic read-only catalog and bounded outcome-blind native history/quotes. Private vectors encrypted; no orders or protected forward.'});checkpoints=[];quality=[];provenance=[];bars={}
  def persist(value,name):return store.encrypted(e.w.old.crypto.strict_json(e.a.enc(value)),name)
  try:
   PHASE='AUTHENTIC_COMPLETE_CURRENT_BROKER_CATALOG';col.connect();cat=col.catalog();rows=c.identities(cat);g=econ.graph(rows)
   for r in rows:
    if r['research_contract_eligible']:
     f=cat['full'][str(r['sid'])];cc=econ.currencies(r,f)
     if any(econ.route(x,'EUR',g) is None for x in cc) or (int(f['commissionType'])==1 and econ.route(r['quote'],'USD',g) is None):r['reasons'].append('CURRENT_NATIVE_FX_GRAPH_NO_ROUTE');r['research_contract_eligible']=False
   checkpoints.append(persist({'schema':'mxm.wide.private.catalog.v1','source_head':h,'catalog':cat,'identities':rows,'counts':dict(col.counts)},'catalog.mxmenc'))
   probe=c.stratified(rows,96,8,primary_ids);PHASE='OUTCOME_BLIND_FOUR_PERIOD_H1_QUALITY';windows=[(datetime(y,m,d,tzinfo=timezone.utc).timestamp(),datetime(y,m,d,tzinfo=timezone.utc).timestamp()+7*86400) for y,m,d in ((2024,11,4),(2025,5,5),(2025,11,3),(2026,5,4))]
   for ordinal,r in enumerate(probe):
    sid=r['sid'];f=cat['full'][str(sid)];zz={};qq=[]
    for frm,to in windows:
     frm,to=int(frm),int(to)
     if sid in native and frm>=min(native[sid]):got={t:v for t,v in native[sid].items() if frm<=t<to};rec=[];status='REUSED_AUTHENTIC_M5_AGGREGATION'
     else:got,rec,status=col.h1(sid,int(f['digits']),frm,to)
     zz.update(got);provenance.extend(rec);qq.append({'from':frm,'to':to,'rows':len(got),'status':status})
    quality.append({'sid':sid,'windows':qq,'pass':all(q['rows']>=20 and q['status'] in ('COMPLETE_EXACT_WINDOW','REUSED_AUTHENTIC_M5_AGGREGATION') for q in qq)});bars[sid]=zz
    if ordinal%12==0:print(json.dumps({'phase':'FOUR_PERIOD_QUALITY','ordinal':ordinal,'requests':dict(col.counts),'outcomes_public':False}),flush=True)
   supported={q['sid'] for q in quality if q['pass']};eligible_probe=[r for r in probe if r['sid'] in supported];selected=c.stratified(eligible_probe,48,8,primary_ids);chosen_ids={r['sid'] for r in selected}
   byid={r['sid']:r for r in rows};references=[byid[s] for s in (1,2,250) if s in byid and s not in chosen_ids];research=selected+references;chosen_ids|={r['sid'] for r in references};PHASE='JUSTIFIED_TWO_YEAR_H1_DEPTH'
   for ordinal,r in enumerate(research):
    sid=r['sid'];f=cat['full'][str(sid)];zz=bars.get(sid,{});receipts=[]
    if sid in native:zz=dict(native[sid])|zz
    # Existing exact quality-window and native rows are reused; request only the chronological complement.
    covered=[(int(q['from']),int(q['to'])) for q in next((x['windows'] for x in quality if x['sid']==sid),[]) if q['status'] in ('COMPLETE_EXACT_WINDOW','REUSED_AUTHENTIC_M5_AGGREGATION')]
    if sid in native:covered.append((min(native[sid]),k.END))
    intervals=[];cursor=k.START
    for lo,hi in sorted(covered):
     if lo>cursor:intervals.append((cursor,min(lo,k.END)))
     cursor=max(cursor,hi)
    if cursor<k.END:intervals.append((cursor,k.END))
    for lo,hi in intervals:
     for frm in range(lo,hi,84*86400):
      to=min(frm+84*86400,hi);got,rec,status=col.h1(sid,int(f['digits']),frm,to);receipts.extend(rec)
      for t,v in got.items():need(t not in zz or zz[t]==v,'REUSED_H1_CONFLICT');zz[t]=v
      if status!='COMPLETE_EXACT_WINDOW':provenance.append({'sid':sid,'from':frm,'to':to,'incomplete_status':status})
    bars[sid]=zz;asset=persist({'schema':'mxm.wide.private.h1.v1','source_head':h,'identity':r,'bars':{str(t):v for t,v in zz.items()},'receipts':receipts,'same_native_account':True,'support':hsupport(zz)},'h1-'+str(sid)+'.mxmenc');checkpoints.append(asset)
    print(json.dumps({'phase':'H1_DEPTH_AUTHENTICATED','ordinal':ordinal+1,'requests':dict(col.counts),'outcomes_public':False}),flush=True)
   # Collection cohort is chosen from features and known current schedules only, before new model outcomes.
   PHASE='PREDECLARED_QUOTE_COHORT_BEFORE_MODEL_COMPARISONS';quote_cohort=[];required=set();eligibility_unknown=Counter()
   for r in research:
    sid=r['sid'];f=cat['full'][str(sid)];horizon=k.horizon(r['class']);tt=sorted(bars[sid]);cc=econ.currencies(r,f);paths=[econ.route(x,'EUR',g) for x in cc]+([econ.route(r['quote'],'USD',g)] if int(f['commissionType'])==1 else [])
    fxids={z[0] for path in paths if path is not None for z in path}
    for w in k.QUOTE_WEEKS:
     clocks=[t for t in range(k.SCORE,k.END,3600) if k.iso(t)==w and k.features(bars[sid],t,tt) and c.schedule_state(t+300,f,{})=='OPEN_CURRENT_SCHEDULE_PROXY' and c.schedule_state(t+300+horizon*3600,f,{})=='OPEN_CURRENT_SCHEDULE_PROXY']
     if not clocks:eligibility_unknown['NO_CAUSAL_FEATURE_CURRENT_SCHEDULE_CLOCK']+=1;continue
     t=clocks[0];quote_cohort.append({'sid':sid,'t':t,'h':horizon,'iso':w,'class':r['class']});required.update((s,u) for s in {sid}|fxids for u in (t+300,t+300+2*3600,t+300+horizon*3600) if u<k.END)
   new_required=required-existing_quote_keys;need(len(new_required)*2<=10000,'WHOLE_PREDECLARED_QUOTE_COHORT_CAP')
   for ordinal,(sid,t) in enumerate(sorted(new_required,key=lambda x:(x[1],x[0]))):
    quotes[(sid,t)]=col.quote(sid,t)
    if ordinal%100==0:print(json.dumps({'phase':'PREDECLARED_EXACT_QUOTES','ordinal':ordinal,'requests':dict(col.counts),'outcomes_public':False}),flush=True)
   checkpoints.append(persist({'schema':'mxm.wide.private.quotes.v1','source_head':h,'quote_cohort':quote_cohort,'required':sorted(required),'quotes':[quotes[q] for q in sorted(required)],'counts':dict(col.counts),'no_outcome_selection':True,'cohort_abstentions':dict(eligibility_unknown)},'quotes.mxmenc'))
  finally:col.close()
  PHASE='NEW_NONLINEAR_AND_MAGNITUDE_NUMERIC_EXECUTION';allrows=[];peridentity=[];cohort_keys={(r['sid'],r['t']) for r in quote_cohort};forecasts_for_quotes=[]
  for ordinal,r in enumerate(research):
   sid=r['sid'];rr=k.observations(bars[sid],r['class'])
   for x in rr:x.update(sid=sid,**{'class':r['class']})
   for fam in k.NAMES:
    own=[x for x in rr if x['family']==fam];peridentity.append({'sid':sid,'symbol':r['symbol'],'class':r['class'],'family':fam,'horizon':k.horizon(r['class']) if fam==k.NAMES[0] else 2,'report':k.report(own,fam)})
   forecasts_for_quotes.extend(x for x in rr if x['family']==k.NAMES[0] and (sid,x['t']) in cohort_keys);allrows.extend(thin(rr));del rr
   print(json.dumps({'phase':'NEW_NUMERIC_INFORMATION','ordinal':ordinal+1,'private_outcomes_public':False}),flush=True);e.w.old.budget(maxwall=6500,maxcpu=5000,maxkib=3145728)
  reports={}
  for fam in k.NAMES:
   own=[r for r in allrows if r['family']==fam];reports[fam]={}
   for view,ids in [('staged_broad_research', {r['sid'] for r in selected}),('native_reference',{1,2,250}),('all_executed',chosen_ids)]:
    rr=[r for r in own if r['sid'] in ids];reports[fam][view]={'report':k.report(rr,fam),'clustered':k.clustered(rr,fam)}
   reports[fam]['all_classes']={cls:{'report':k.report([r for r in own if r['class']==cls],fam),'clustered':k.clustered([r for r in own if r['class']==cls],fam)} for cls in sorted({r['class'] for r in own})}
  PHASE='NATIVE_MULTI_CURRENCY_COSTS_AND_CAUSAL_CAPITAL';economic_rows=econ.evaluate(forecasts_for_quotes,rows,cat,quotes);economic=econ.report(economic_rows);portfolio=econ.portfolio(economic_rows);support={str(s):hsupport(bars[s]) for s in chosen_ids};catalogcounts={'offered':len(rows),'archived':len(cat['archived']),'class_counts':dict(Counter(r['class'] for r in rows)),'contract_risk_eligible':sum(r['research_contract_eligible'] for r in rows),'exclusion_reason_counts_overlapping':dict(Counter(v for r in rows for v in r['reasons'])),'quality_probed':len(probe),'quality_passed':len(supported),'staged_deep':len(selected),'reference_only_added':len(references),'new_to_PRIMARY145':sum(r['sid'] not in primary_ids for r in selected),'not_selected_resource_budget_not_rejected':sum(r['research_contract_eligible'] for r in rows)-len(selected)}
  complete_weeks=k.weeks();upper={str(r['sid']):{'holding_hours':k.horizon(r['class']),'geometric_ceiling_per_UTC_week':168//k.horizon(r['class']),'quote_cohort_positions_per_complete_week':{w:sum(x['sid']==r['sid'] and x['iso']==w for x in economic_rows) for w in complete_weeks}} for r in research}
  summary={'schema':'mxm.private.wide.greenfield.summary.v1','source_head':h,'design_commit':a['design_commit'],'classification':'EXPLORATORY_INFORMATION_ONLY_NO_ALPHA_CERTIFIED','catalog':catalogcounts,'research_identities':research,'quality':quality,'authentic_data_support':support,'source_provenance':[hp,qp,vp],'primary145_retained_not_universe_limit':True,'native_reused_H1_rows':{str(s):len(v) for s,v in native.items()},'data_checkpoint_release_id':store.release['id'],'data_checkpoints':checkpoints,'requests':dict(col.counts),'families':reports,'economic':slim_econ(economic),'portfolio':{**portfolio,'report':slim_econ(portfolio['report'])},'HARD21':{'demonstrated':False,'supported_NET_trades':0,'instrument_upper_bounds':upper,'portfolio_geometric_weekly_upper_using_fastest_directional_horizon':max(168//k.horizon(r['class']) for r in research) if research else 0,'independent_opportunities':'UNIDENTIFIED;HOURLY_FORECASTS_AND_SIMULTANEOUS_ASSETS_NOT_TRADES'},'previous_report_identity':a['previous_report_identity'],'orders':0,'fills':0,'protected_forward':False,'cloud_changes':False,'historical_fees_funding_fills':'UNKNOWN;CURRENT_CONTRACT_SCENARIOS;0_FUNDING_NOT_HISTORICAL_ZERO','bindings':a['bindings']}
  full={'summary':summary,'per_identity_reports':peridentity,'all_economic_cohort_entries':economic_rows,'all_quotes_required':[quotes[q] for q in sorted(required)],'quality_provenance':provenance,'raw_catalog':cat,'all_current_identity_status':rows,'closed_scientific_exacts_untouched':True,'source_checkpoints':checkpoints}
  PHASE='ENCRYPTED_AUTHENTIC_PUBLICATION';rt.output(h,a,tmp,key,'widegreenfield',full,summary)
  # Compact relay retains all aggregate weeks/blocks and per-identity data support; full vectors stay owner-encrypted.
  relaysummary={n:v for n,v in summary.items() if n not in ('quality','data_checkpoints')};relaysummary['families']={fam:{v:report for v,report in views.items() if v!='all_classes'} for fam,views in reports.items()};relaysummary['HARD21']['instrument_upper_bounds']={s:{n:v for n,v in z.items() if n!='quote_cohort_positions_per_complete_week'} for s,z in upper.items()};relaysummary['data_checkpoints']=checkpoints
  relay(h,a,tmp,relaysummary)
if __name__=='__main__':
 try:main()
 except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(1)
