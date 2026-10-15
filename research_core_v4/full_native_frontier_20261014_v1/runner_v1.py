"""Finite full-frontier Actions campaign, durable cold-process continuation."""
import os,json,pathlib,tempfile,subprocess,base64,gzip,hashlib,time,math,statistics,sqlite3,re
from datetime import datetime,timezone
from collections import Counter,defaultdict
from cryptography.hazmat.primitives import serialization,hashes
from cryptography.hazmat.primitives.asymmetric import padding
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.cost_frequency_discovery_v1.collector_v1 import Collector
from . import accounting_v1 as fx
from research_core_v4.owner_frontier_v1.execute_historical_quotes_v1 import m,enums
from m6.cost_evidence import decode_ctrader_tick_page
from . import archive_v1 as ar,kernel_v1 as k
E=rt.e;P='research_core_v4/full_native_frontier_20261014_v1/';WF='.github/workflows/mxm-full-native-frontier-20261014-v1.yml';PHASE='GATE';DB=None

def need(x,c):E.w.old.need(bool(x),c)
def encode(x):return E.a.enc(x)
def norm(x):return json.loads(encode(x))
def gate():
 h=os.environ['GITHUB_SHA'];a=json.loads((E.a.ROOT/(P+'EXECUTION_V1.json')).read_text());E.w.v2.runtime(h);E.a.ancestor(a['base_head'],h)
 need(a['authority']=='EXPLICIT_OWNER_FULL_NATIVE_FRONTIER_AUTONOMOUS_20261014','AUTHORITY');need(os.environ['GITHUB_RUN_ATTEMPT']=='1','NO_UNCONTROLLED_RETRY');need(os.environ['GITHUB_WORKFLOW_REF']==E.w.old.REPO+'/'+WF+'@refs/heads/'+E.w.old.BRANCH,'WORKFLOW');need(datetime.now(timezone.utc).isoformat()<a['expires_utc'],'EXPIRED')
 for p,sha in a['bindings'].items():need(E.w.old.filehash(p)==sha,'SOURCE_BINDING')
 old=set(subprocess.check_output(['git','ls-tree','-r',a['base_head']],text=True).splitlines());new=set(subprocess.check_output(['git','ls-tree','-r',h],text=True).splitlines());need(old<=new,'ACCEPTED_FILES_CHANGED')
 claim=a['invocation_id']+'-'+os.environ['GITHUB_RUN_ID']+'-'+os.environ['GITHUB_JOB'];need(not E.w.v2.existing_ref(claim),'JOB_ALREADY_CONSUMED');E.w.old.api('git/refs',{'ref':'refs/tags/'+claim,'sha':h});return h,a

def release_for(h,a):
 matches=E.w.v2.existing_ref(a['release_tag'])
 if matches:return E.w.old.api('releases/tags/'+a['release_tag'])
 return E.w.old.api('releases',{'tag_name':a['release_tag'],'target_commitish':h,'name':'MXM durable full native economic frontier','prerelease':True,'body':json.dumps({'schema':'mxm.full.native.frontier.public.v1','source_head':h,'state':'BOOTSTRAP_PENDING','new_alpha':False,'HARD21':False,'orders':0})})
class FrontierStore(E.w.old.GitHubStore):
 def restore(self,meta):
  asset=E.w.old.api('releases/assets/'+str(meta['id']));need(asset['name']==meta['name'] and asset['size']==meta['size'] and asset['digest']=='sha256:'+meta['ciphertext_sha256'],'REMOTE_ASSET_METADATA')
  blob=E.w.old.download(asset['browser_download_url'],meta['size']);need(E.a.sha(blob)==meta['ciphertext_sha256'],'REMOTE_CIPHER_SHA');packed=E.w.old.crypto.decrypt_package(blob,private_key=self.key,expected_public_spki_sha256=E.w.old.FP,temp_parent=self.tmp);need(E.a.sha(packed)==meta['gzip_sha256'],'REMOTE_PACKED_SHA');raw=gzip.decompress(packed);need(E.a.sha(raw)==meta['canonical_sha256'],'REMOTE_CANONICAL_SHA');obj=E.w.old.crypto.strict_json(raw);need(encode(obj)==raw,'REMOTE_CANONICAL');return obj

def asset_value(store,obj,name):return store.encrypted(norm(obj),name)
def update_body(store,body):
 E.w.old.api('releases/'+str(store.release['id']),{'body':json.dumps(body,sort_keys=True)},method='PATCH');store.release=E.w.old.api('releases/'+str(store.release['id']))
def shard_export(db,groups,store,st,label):
 for group in sorted(groups):
  b=db.execute('SELECT * FROM bar WHERE s%64=? ORDER BY s,t',(group,)).fetchall();q=db.execute('SELECT * FROM tick WHERE s%64=? ORDER BY s,k,t,p',(group,)).fetchall();sp=db.execute('SELECT * FROM span WHERE s%64=? ORDER BY s,k,a,b',(group,)).fetchall()
  meta=asset_value(store,{'schema':'mxm.frontier.data.shard.v1','group':group,'bars':b,'ticks':q,'spans':sp},'data-g'+str(group)+'-'+label+'.mxmenc');st['shards'][str(group)]=meta
 db.commit()
def persist(db,store,st,label,groups=()):
 shard_export(db,groups,store,st,label)
 for group in sorted(st.pop('_record_dirty',set())):
  vv={sid:r for sid,r in st['identity_records'].items() if int(sid)%64==group};st['record_shards'][str(group)]=asset_value(store,{'records':vv},'records-g'+str(group)+'-'+label+'.mxmenc')
 st['generation']+=1;st['last_run']=int(os.environ['GITHUB_RUN_ID']);st['last_job']=os.environ['GITHUB_JOB'];snapshot={key:value for key,value in st.items() if key!='identity_records'};meta=asset_value(store,snapshot,'manifest-'+str(st['generation'])+'-'+label+'.mxmenc');body={'schema':'mxm.full.native.frontier.public.v1','source_head':store.head,'state':st['phase'],'generation':st['generation'],'run_id':st['last_run'],'job':st['last_job'],'current_journal':meta,'release_id':store.release['id'],'catalog':5326,'eligible':len(st['eligible']),'identities_completed':st.get('identity_cursor',0),'identities_total':len(st['eligible']),'new_requests':st['requests'],'remaining':max(0,len(st['eligible'])-st.get('identity_cursor',0)),'bootstrap_owner_report_readback':st['original_report_verified'],'resume_proofs':len(st['resume_proofs']),'pilot_executed':st.get('pilot') is not None,'alpha_certified':False,'HARD21':False,'orders':0};update_body(store,body);print(json.dumps(body),flush=True)
 return meta

def restore(db,store):
 body=json.loads(store.release['body']);st=store.restore(body['current_journal'])
 for meta in st['shards'].values():
  data=store.restore(meta);db.executemany('INSERT INTO bar VALUES(?,?,?,?,?,?,?)',data['bars']);db.executemany('INSERT INTO tick VALUES(?,?,?,?)',data['ticks']);db.executemany('INSERT INTO span VALUES(?,?,?,?,?)',data['spans'])
 db.commit();st['identity_records']={}
 for meta in st.get('record_shards',{}).values():st['identity_records'].update(store.restore(meta)['records'])
 st['resume_proofs'].append({'from_generation':st['generation'],'from_run':st['last_run'],'from_job':st['last_job'],'to_run':int(os.environ['GITHUB_RUN_ID']),'to_job':os.environ['GITHUB_JOB'],'recovered_manifest_sha256':body['current_journal']['canonical_sha256'],'bars':db.execute('SELECT count(*) FROM bar').fetchone()[0],'ticks':db.execute('SELECT count(*) FROM tick').fetchone()[0],'state':'VERIFIED_REMOTE_OWNER_COLD_PROCESS_RESUME'})
 # A crash between before-send journal and durable raw receipt is not silently
 # retried. These uncertain wire windows remain explicit terminal support gaps.
 for req in st.pop('pending_requests',[]):
  ar.span(db,req['s'],req['k'],req['a'],req['b'],'UNCERTAIN_WIRE_INTERRUPTION_NO_DUPLICATE_RETRY');st['uncertain_wire'].append(req)
 return st

def bootstrap(db,store,a,tmp,key):
 global PHASE
 PHASE='ORIGINAL_REPORT_OWNER_READBACK';c=json.loads((E.a.ROOT/(P+'ORIGINAL_REPORT_PRESERVATION_V1.json')).read_text());blob=base64.b64decode((E.a.ROOT/(P+'original-report-owner.mxmenc.b64')).read_bytes());need(E.a.sha(blob)==c['ciphertext_sha256'],'ORIGINAL_REPORT_CIPHER');raw=gzip.decompress(E.w.old.crypto.decrypt_package(blob,private_key=key,expected_public_spki_sha256=E.w.old.FP,temp_parent=tmp));need(E.a.sha(raw)==c['canonical_payload_sha256'],'REPORT_PAYLOAD');report=json.loads(raw);need(E.a.sha(base64.b64decode(report['file_bytes_b64']))==c['original_sha256'],'ORIGINAL_REPORT_BYTES');asset_value(store,report,'original-complete-report-owner.mxmenc')
 source,catproof=load_asset(key,E.w.old.FP,tmp,a['catalog_source']);pre,_=load_asset(key,E.w.old.FP,tmp,a['precheck']);statuses=pre['summary']['statuses'];rows={int(r['sid']):r for r in source['identities']};cat=source['catalog'];need(len(rows)==len(statuses)==5326,'CATALOG');eligible=sorted(s['sid'] for s in statuses if s['structural_eligible']);need(len(eligible)==1562,'ACCEPTED_ELIGIBLE')
 PHASE='GLOBAL_ARCHIVE_RECONCILIATION';archive=ar.global_reconcile(db,key,E.w.old.FP,tmp,E.a.ROOT)
 st={'schema':'mxm.full.native.frontier.durable.manifest.v1','source_head':store.head,'phase':'READY_FOR_NATIVE_WORK','generation':0,'catalog':cat,'rows':rows,'eligible':eligible,'original_statuses':statuses,'original_report_verified':True,'catalog_provenance':catproof,'archive':archive,'shards':{},'identity_cursor':0,'identity_records':{},'record_shards':{},'requests':{'M5':0,'BID_ASK':0},'op_counter':0,'resume_proofs':[],'uncertain_wire':[],'pending_requests':[],'pilot':None,'candidate_review':a['candidate_review'],'errors':[],'accounting_79_reconciliation':None}
 # First source regression is a semantic readback only: the 79 accepted pairs
 # and four missing bps denominators are classified from preserved accounting.
 old,proof=load_asset(key,E.w.old.FP,tmp,a['completed_economic_result']);rr=old['records'];paired=[r for r in rr if all(r['two_direction_accounting']['2'][d] is not None for d in ('long','short'))];need(len(paired)==79,'ACCEPTED_79')
 missing=[]
 for r in paired:
  z=r['two_direction_accounting']['2']['long']
  if z['total_cost_bps_entry_notional'] is None:missing.append({'sid':r['sid'],'t':r['t'],'entry_notional_state':r['reference']['2']['state'],'entry_quote_valid':r['reference']['2']['state']!='NATIVE_QUOTE_NOT_FRESH_COMPLETE','missing_bps_cause':'NO_VALID_NATIVE_ENTRY_NOTIONAL_EUR_FX_PATH;EXIT_PNL_AND_FEE_CONVERSION_CAN_EXIST_INDEPENDENTLY','cash_accounting_eur_preserved':True})
 need(len(missing)==4,'ACCEPTED_4_DENOMINATORS');st['accounting_79_reconciliation']={'source':proof,'paired':79,'bps_denominator_present':75,'missing_denominators':missing,'original_result_not_recomputed_or_changed':True}
 persist(db,store,st,'bootstrap',set(range(64)));return st

def bars_for(db,s):return {t:[o,h,l,c,v] for t,o,h,l,c,v in db.execute('SELECT t,o,h,l,c,v FROM bar WHERE s=? ORDER BY t',(s,))}
def side_for(db,s,side,t,ttl=1800000):return [(tt,p) for tt,p in db.execute('SELECT t,p FROM tick WHERE s=? AND k=? AND t BETWEEN ? AND ? ORDER BY t,p',(s,side,t-ttl,t))]
def qpoint(db,s,t,strict=False):
 z=k.quote_state(side_for(db,s,'bid',t*1000),side_for(db,s,'ask',t*1000),t*1000,5000 if strict else 300000,2000 if strict else None)
 return z

def acquire_m5(db,s,f,col,st,store,deadline):
 gaps=ar.missing(db,s,'M5',ar.LOW*1000,ar.END*1000-1);receipts=[];changed=set()
 for lo,hi in gaps:
  if time.monotonic()>deadline:return False,receipts,changed
  st['op_counter']+=1;st['pending_requests']=[{'s':s,'k':'M5','a':lo,'b':hi}];persist(db,store,st,'before-m5-'+str(st['op_counter']))
  b,raw,status=col.m5(s,int(f['digits']),lo//1000,(hi+1)//1000);st['requests']['M5']+=sum('raw_response_envelope_b64' in x for x in raw)
  for t,z in b.items():ar.putbar(db,s,t,z)
  ar.span(db,s,'M5',lo,hi,status);changed.add(s%64);receipts.append({'s':s,'from_ms':lo,'to_ms':hi,'state':status,'rows':len(b),'receipts':raw});st['pending_requests']=[];asset_value(store,{'schema':'mxm.authentic.native.m5.increment.v1','receipts':receipts},'m5-op-'+str(st['op_counter'])+'.mxmenc');persist(db,store,st,'after-m5-'+str(st['op_counter']),changed);receipts=[];changed=set()
 return True,receipts,changed

def needed_routes(row,f,g):
 paths=[fx.route(ccy,'EUR',g) for ccy in fx.currencies(row,f)]
 if int(f['commissionType'])==1:paths.append(fx.route(row['quote'],'USD',g))
 return paths,{edge[0] for p in paths if p is not None for edge in p}

def acquire_quotes(db,keys,col,st,store,deadline):
 ops=[]
 for s,t in sorted(keys,key=lambda x:(x[1],x[0])):
  for side in ('bid','ask'):
   for lo,hi in ar.missing(db,s,side,(t-1800)*1000,t*1000):ops.append({'s':s,'k':side,'a':lo,'b':hi})
 for start in range(0,len(ops),64):
  if time.monotonic()>deadline:return False
  batch=ops[start:start+64];st['op_counter']+=1;st['pending_requests']=batch;persist(db,store,st,'before-quotes-'+str(st['op_counter']));raw=[];groups=set();broken=False
  for req in batch:
   groups.add(req['s']%64)
   if st['requests']['BID_ASK']>=st['campaign_tick_cap']:raise RuntimeError('FINITE_CAMPAIGN_TICK_CAP')
   try:
    q=m.ProtoOAGetTickDataReq(ctidTraderAccountId=col.aid,symbolId=req['s'],type=enums.BID if req['k']=='bid' else enums.ASK,fromTimestamp=req['a'],toTimestamp=req['b']);st['requests']['BID_ASK']+=1;res=col.send(q,True)
    if isinstance(res,m.ProtoOAErrorRes):
     ar.span(db,req['s'],req['k'],req['a'],req['b'],'PROVIDER_'+res.errorCode);raw.append({'request':req,'state':'PROVIDER_ERROR','provider_code':res.errorCode});continue
    need(isinstance(res,m.ProtoOAGetTickDataRes) and res.IsInitialized() and res.ctidTraderAccountId==col.aid,'QUOTE_RESPONSE_BINDING');enc=[{'timestamp':int(x.timestamp),'tick':int(x.tick)} for x in res.tickData];n=ar.tickrows(db,req['s'],req['k'],enc,req['a'],req['b']) or 0;ar.span(db,req['s'],req['k'],req['a'],req['b'],'PARTIAL_NATIVE_SUPPORT_HASMORE' if res.hasMore else 'COMPLETE_NATIVE_QUOTE_RESPONSE' if n else 'EMPTY_WINDOW_NO_QUOTE_UPDATE');raw.append({'request':req,'response_b64':base64.b64encode(res.SerializeToString()).decode(),'encoded':enc,'hasMore':bool(res.hasMore),'rows':n});groups.add(req['s']%64)
   except Exception as ex:
    raw.append({'request':req,'state':'UNKNOWN_WITH_EXACT_CAUSE','cause':'TRANSPORT_OR_PROTOCOL_RESPONSE_UNRESOLVED','exception_class':type(ex).__name__});ar.span(db,req['s'],req['k'],req['a'],req['b'],'UNKNOWN_TRANSPORT_OR_PROTOCOL');groups.add(req['s']%64);broken=True;break
  for req in batch[len(raw):]:ar.span(db,req['s'],req['k'],req['a'],req['b'],'UNCERTAIN_BATCH_STOP_NOT_SENT_NO_RETRY');st['uncertain_wire'].append(req);groups.add(req['s']%64)
  meta=asset_value(store,{'schema':'mxm.native.quote.increment.raw.responses.v1','requests':raw,'no_duplicate_known_accepted_interval':True},'quotes-op-'+str(st['op_counter'])+'.mxmenc');st.setdefault('raw_quote_checkpoints',[]).append(meta);st['pending_requests']=[];persist(db,store,st,'after-quotes-'+str(st['op_counter']),groups)
  if broken:raise RuntimeError('TRANSPORT_STOP_AFTER_DURABLE_PARTIAL')
 return True

def fxquotes(db,ids,times,strict=False):
 out={}
 for sid in ids:
  for t in times:
   z=qpoint(db,sid,t,strict)
   if z['valid']:out[sid,t]={'symbol_id':sid,'boundary_ms':t*1000,'state_expiry_ms':5000 if strict else 300000,'sides':{side:{'state':'AUTHENTIC_CAUSAL_QUOTE_RECONSTRUCTED_STATE','price':z[side],'timestamp_ms':z[side+'_time_ms'],'age_ms':t*1000-z[side+'_time_ms']} for side in ('bid','ask')}}
 return out

def economic_event(db,row,f,ev,g,bars):
 paths,routeids=needed_routes(row,f,g);ids={row['sid']}|routeids;t=ev['t'];quotes=fxquotes(db,ids,(t,t+900));q0=qpoint(db,row['sid'],t);q1=qpoint(db,row['sid'],t+900);strict0=qpoint(db,row['sid'],t,True);strict1=qpoint(db,row['sid'],t+900,True);feat=k.feature(bars,t,ev['open_proxy'],ev['kind']);out={**ev,'sid':row['sid'],'class':row['class'],'iso':k.iso(t),'feature':feat,'quote_state':q0,'exit_quote_state':q1,'strict_entry':strict0,'strict_exit':strict1,'entry':{'eligible':False,'state':'UNKNOWN_WITH_EXACT_CAUSE'},'accounts':None}
 if ev.get('holiday_proxy','').startswith('CURRENT_NATIVE_HOLIDAY_PROXY_CLOSED'):out['entry'].update(state='UNKNOWN_WITH_EXACT_CAUSE',cause='CURRENT_NATIVE_HOLIDAY_FLAGS_CLOSED;NOT_HISTORICAL_ASOF_CERTIFIED');return out
 if not q0['valid']:out['entry']['state']='EMPTY_WINDOW_NO_QUOTE_UPDATE' if q0['state']=='NO_CAUSAL_SEED' else 'PARTIAL_NATIVE_SUPPORT';return out
 if not feat['supported']:out['entry']['state']='PARTIAL_NATIVE_SUPPORT';out['entry']['cause']=feat['reason'];return out
 if any(p is None for p in paths):out['entry']['state']='FX_OR_CONTRACT_UNRESOLVED';return out
 notional=fx.convert(-row['min_units']*q0['mid'],row['quote'],'EUR',t,quotes,g);spread=fx.convert(-row['min_units']*(q0['ask']-q0['bid']),row['quote'],'EUR',t,quotes,g);fees=[fx.commission(row,f,row['min_units'],q0[p],t,quotes,g) for p in ('bid','ask')]
 if notional is None or spread is None or any(x is None for x in fees):out['entry']['state']='FX_OR_CONTRACT_UNRESOLVED';return out
 notional=-notional;rate=int(f['pnlConversionFeeRate'])/10000 if row['quote']!='EUR' else 0.;cost=-spread+.0004*notional+(sum(fees)+.10/96)/(1-rate);gap=max(5.,feat['max_observed_prior_gap_bps']);risk=cost+notional*max(feat['tail_bps']*math.sqrt(3),gap)/10000;scale=notional*feat['scale_bps']*math.sqrt(3)/10000
 en={'state':'COMPLETE_NATIVE_SUPPORT','eligible':risk<=2 and row['margin_eur']<=80 and cost<=scale,'notional_eur':notional,'break_even_eur':cost,'break_even_bps':cost/notional*10000,'planned_risk_eur':risk,'margin_eur':row['margin_eur'],'preentry_scale_eur':scale,'gap_stress_bps':gap,'stop_loss_guaranteed':False,'historical_cost_terms':'UNKNOWN_CURRENT_TERMS_PLUS_2BPS_PER_SIDE_AND_010EUR_DAY_STRESS','unobserved_intratrade_risk':'UNKNOWN_NO_FAKE_STOP_FILL'};out['entry']=en
 # Accounting is deferred to the first separately qualified, frozen candidate.
 out['_native_accounting_context']={'quote_ids':sorted(ids),'paired_reference':q1['valid'] and all(fx.point(quotes.get((sid,t+900))) is not None for sid in ids)}
 return out

def qualifying(records):
 from research_core_v4.remediation_p0_p4_20261015.science import qualifying as successor_qualifying
 return successor_qualifying(records)

def pilot(db,st,store,a):
 rr=[r for s in st['identity_records'].values() for r in s.get('events',[])];q=qualifying(rr)
 if not q['gate_pass'] or st['pilot'] is not None:return
 # The source/design were frozen before acquisition. Only support and ex-ante
 # economic quantities pass this gate; no side payoff has been read above.
 native_parity=parity(db,st,store.tmp)
 plan={'native_preoutcome_kernel_parity':native_parity,'schema':'mxm.full.frontier.single.pilot.arm.v1','mechanism':a['mechanism'],'qualification':q,'source_head':store.head,'design_sha256':E.w.old.filehash(P+'DESIGN_V1.json'),'model_feature_calls_closed_exact':0,'classification':'DEVELOPMENT_ADAPTIVE_EXPLORATORY_NO_CLOUD_OR_FORWARD_PROMOTION','first_candidate_only':True};arm=asset_value(store,plan,'single-qualified-pilot-arm.mxmenc');rows={int(s):r for s,r in st['rows'].items()};g=fx.graph(list(rows.values()));priced=[];censored=[]
 for ev in sorted(rr,key=lambda r:(r['t'],r['sid'])):
  if not ev['entry'].get('eligible'):continue
  row=rows[ev['sid']];f=st['catalog']['full'][str(ev['sid'])];ids=ev['_native_accounting_context']['quote_ids'];quotes=fxquotes(db,ids,(ev['t'],ev['t']+900));values={}
  for name,d in [('model',ev['feature']['model_side']),('gap',ev['feature']['gap_side']),('momentum',ev['feature']['momentum_side'])]:
   if not d:values[name]={'net_eur':0.,'cash_abstention_by_design':True};continue
   z=fx.account(d,row,f,ev['t'],ev['t']+900,.25,quotes,g,2,.10)
   if z is not None:
    q0=fx.point(quotes.get((row['sid'],ev['t'])));q1=fx.point(quotes.get((row['sid'],ev['t']+900)));mid=fx.convert(d*row['min_units']*(q1['mid']-q0['mid']),row['quote'],'EUR',ev['t']+900,quotes,g);native=fx.convert(d*row['min_units']*((q1['bid'] if d>0 else q1['ask'])-(q0['ask'] if d>0 else q0['bid'])),row['quote'],'EUR',ev['t']+900,quotes,g);z.update(midpoint_gross_eur=mid,spread_drag_eur=mid-native,slippage_drag_eur=native-z['gross_eur'])
   values[name]=z
  if any(z is None for z in values.values()):censored.append({'sid':ev['sid'],'t':ev['t'],'cause':'ENTRY_EXIT_NATIVE_FX_OR_COST_NA'});continue
  priced.append({'event':ev,'values':values})
 def agg(z):
  keys=('midpoint_gross_eur','spread_drag_eur','slippage_drag_eur','entry_commission_eur','exit_commission_eur','pnl_conversion_fee_eur','funding_stress_eur','net_eur');out={'paired':len(z),'model_active':sum(r['event']['feature']['model_side']!=0 for r in z)}
  for name in ('model','gap','momentum'):out[name]={field:sum(r['values'][name].get(field,0.) for r in z) if z else None for field in keys}
  out['model_minus_gap_net_eur']=out['model']['net_eur']-out['gap']['net_eur'] if z else None;out['model_minus_momentum_net_eur']=out['model']['net_eur']-out['momentum']['net_eur'] if z else None;return out
 summary=agg(priced);weekly={w:agg([r for r in priced if r['event']['iso']==w]) for w in sorted({r['iso'] for r in rr})};cash=200.;active=[];closed=[];selected=[];halt=None
 for ev in sorted(rr,key=lambda r:(r['t'],r['sid'])):
  t=ev['t']
  for z in sorted([r for r in active if r['event']['t']+900<=t],key=lambda r:(r['event']['t'],r['event']['sid'])):
   value=z['value']
   if value is None:halt='FIRST_SELECTED_UNKNOWN_EXIT_NO_REPLACEMENT';break
   cash+=value['net_eur'];closed.append(z);active.remove(z)
  if halt:break
  if not (ev['entry'].get('eligible') and ev['feature'].get('model_side')):continue
  if any(r['event']['sid']==ev['sid'] for r in active):continue
  en=ev['entry']
  if sum(r['event']['entry']['planned_risk_eur'] for r in active)+en['planned_risk_eur']>.01*cash or sum(r['event']['entry']['margin_eur'] for r in active)+en['margin_eur']>.40*cash:continue
  row=rows[ev['sid']];qts=fxquotes(db,ev['_native_accounting_context']['quote_ids'],(t,t+900));v=fx.account(ev['feature']['model_side'],row,st['catalog']['full'][str(ev['sid'])],t,t+900,.25,qts,g,2,.10);record={'event':ev,'value':v};active.append(record);selected.append(record)
 if not halt:
  for z in sorted(active,key=lambda r:r['event']['t']):
   if z['value'] is None:halt='FIRST_SELECTED_UNKNOWN_EXIT_NO_REPLACEMENT';break
   cash+=z['value']['net_eur'];closed.append(z)
 st['pilot']={'schema':'mxm.authentic.native.range.acceptance.pilot.result.v1','arm':arm,'qualification':q,'summary':summary,'weekly':weekly,'priced':priced,'censored':censored,'portfolio':{'initial_eur':200,'closed_equity_eur_reference':cash,'selected':len(selected),'closed':len(closed),'halt':halt,'entries_by_ISO_week':dict(Counter(r['event']['iso'] for r in selected)),'actual_orders':0,'actual_fills':0,'dynamic_caps':{'risk_fraction':.01,'margin_fraction':.40,'reserve_fraction':.60},'intratrade_gap_risk_and_stop_fill':'UNIDENTIFIED_NOT_GUARANTEED','HARD21':False},'decision':'CLOSED_NO_PROMOTION_NEGATIVE_EXACT' if priced and (summary['model']['net_eur']<=0 or summary['model_minus_gap_net_eur']<=0 or summary['model_minus_momentum_net_eur']<=0) else 'EXPLORATORY_ONLY_REQUIRES_DISJOINT_CONFIRMATION_AND_CLOUD_PARITY','uncertainty':'DEPENDENT_SYMBOLS_SHARED_FX_DATES_3_WEEKS_PRIOR_ADAPTIVE_EXPOSURE;NO_DEFENSIBLE_CONFIRMATORY_PVALUE_OR_FWER_FROM_THIS_PILOT','actual_Cloud_parity':False,'protected_forward':False}
 meta=asset_value(store,st['pilot'],'single-qualified-pilot-result.mxmenc');st['pilot'].pop('priced');st['pilot']['complete_result']=meta


def process_identity(db,s,st,col,store,a,deadline):
 row=st['rows'][str(s)];f=st['catalog']['full'].get(str(s));record=st['identity_records'].get(str(s),{'sid':s,'events':[],'state':'PENDING','sessions':[]})
 if not f:record.update(state='FX_OR_CONTRACT_UNRESOLVED',cause='ACCEPTED_NATIVE_FULL_CONTRACT_MISSING');st['identity_records'][str(s)]=record;return True
 if not acquire_m5(db,s,f,col,st,store,deadline)[0]:return False
 bars=bars_for(db,s)
 if not bars:record.update(state='UNKNOWN_WITH_EXACT_CAUSE',cause='AUTHENTIC_M5_RESPONSE_EMPTY_IN_REQUIRED_INTERVAL;NOT_GLOBAL_BROKER_UNAVAILABILITY');st['identity_records'][str(s)]=record;return True
 try:sessions=k.schedule_clocks(f,ar.START,ar.END)
 except Exception as ex:record.update(state='FX_OR_CONTRACT_UNRESOLVED',cause='NATIVE_SCHEDULE_TIMEZONE_UNSUPPORTED',exception_class=type(ex).__name__);st['identity_records'][str(s)]=record;return True
 if not sessions:record.update(state='UNKNOWN_WITH_EXACT_CAUSE',cause='NO_CURRENT_WEEKLY_PROXY_SESSION_LONG_ENOUGH;HISTORICAL_SESSION_NOT_CERTIFIED');st['identity_records'][str(s)]=record;return True
 # All relevant native session openings and matched controls, all eligible IDs.
 # No arbitrary symbol cap or future-price performance selection.
 done={r['t'] for r in record['events']};g=fx.graph(list(st['rows'].values()));paths,routeids=needed_routes(row,f,g)
 keys={(sid,t) for ev in sessions if ev['t'] not in done and ev['t']+900<ar.END for sid in {s}|routeids for t in (ev['t'],ev['t']+900)}
 if not acquire_quotes(db,keys,col,st,store,deadline):return False
 for ev in sorted(sessions,key=lambda z:z['t']):
  if ev['t'] in done or ev['t']+900>=ar.END:continue
  er=economic_event(db,row,f,ev,g,bars);record['events'].append(er)
 st['identity_records'][str(s)]=record
 record['sessions']=sessions;record['known_m5_rows']=len(bars);complete=sum(r['entry']['state']=='COMPLETE_NATIVE_SUPPORT' and r.get('_native_accounting_context',{}).get('paired_reference') for r in record['events']);record['state']='COMPLETE_NATIVE_SUPPORT' if len(record['events']) and complete==len(record['events']) else 'PARTIAL_NATIVE_SUPPORT';record['reason_counts']=dict(Counter(r['entry']['state'] for r in record['events']));st['identity_records'][str(s)]=record;return True


def parity(db,st,tmp):
 inputs=[];outputs=[]
 for s in st['identity_records'].values():
  bb=bars_for(db,s['sid'])
  for ev in s.get('events',[]):
   for t in (ev['t'],ev['t']+900):
    b=side_for(db,ev['sid'],'bid',t*1000);a=side_for(db,ev['sid'],'ask',t*1000);b=[r for r in b if r[0]>=max([x[0] for x in b],default=0)-1];a=[r for r in a if r[0]>=max([x[0] for x in a],default=0)-1]
    for strict in (False,True):inputs.append({'bid':b,'ask':a,'t':t*1000,'ttl':5000 if strict else 300000,'skew':2000 if strict else None});outputs.append(k.quote_state(b,a,t*1000,5000 if strict else 300000,2000 if strict else None))
    if ev['feature'].get('supported') and ev['kind']=='REOPEN' and 'prior_session_high' in ev['feature']:
     inputs[-1].update(rangeClose=[bb[ev['open_proxy']+i*300][3] for i in range(3)],priorHigh=ev['feature']['prior_session_high'],priorLow=ev['feature']['prior_session_low']);outputs[-1]['range_side']=ev['feature']['model_side']
 inf=tmp/'parity-input.jsonl';out=tmp/'parity-output.jsonl';inf.write_text(''.join(json.dumps(v)+'\n' for v in inputs));subprocess.run(['dotnet',str(E.a.ROOT/(P+'csharp/bin/Release/net8.0/Replay.dll')),str(inf),str(out)],check=True,stdout=subprocess.DEVNULL)
 native_lines=out.read_text().splitlines()
 need(len(outputs)==len(native_lines),'CSHARP_COUNT')
 if not outputs:return {'state':'UNSUPPORTED_NO_VALID_VECTORS','causal_quote_states':0,'parity_certified':False,'actual_cloud_feed_parity':'NOT_CERTIFIED_NO_DEPLOYMENT_AUTHORIZED'}
 n=0
 for py,line in zip(outputs,native_lines):
  cs=json.loads(line);need(py.keys()==cs.keys(),'CSHARP_FIELDS')
  for key,v in py.items():need(math.isclose(v,cs[key],rel_tol=1e-12,abs_tol=1e-12) if type(v)==float else v==cs[key],'CSHARP_QUOTE_STATE_PARITY')
  n+=1
 need(n==len(outputs),'CSHARP_COUNT');return {'state':'PASS_KERNEL_VALUES_ONLY_EVENT_ID_CERTIFICATION_REQUIRED','parity_certified':False,'causal_quote_states':n,'actual_cloud_feed_parity':'NOT_CERTIFIED_NO_DEPLOYMENT_AUTHORIZED','native_adapter_compilation':'REUSE_EXISTING_ACCEPTED_CTRADER_AUTOMATE_ADAPTER','prediction_observables':'CLOSED_M5_OHLC_NATIVE_SESSION_GAP_PRIOR_RANGE;API_GetBars_AND_GetTicks;NO_EXTERNAL_RUNTIME','side_timestamp_equivalence_limit':'OPEN_API_SIDE_PUBLICATION_VS_NATIVE_JOINT_TICK_CALLBACK_NOT_PROVEN','restart_state':'PURE_KERNEL_RESEEDED_FROM_NATIVE_HISTORY;MISSING_SEED_ABSTAINS;LIVE_POSITIONS_RECONCILIATION_NOT_CERTIFIED_NO_ORDERS'}

def final_report(db,st,store,a,tmp,key):
 rr=[r for v in st['identity_records'].values() for r in v.get('events',[])];valid=sum(r['quote_state'].get('valid',False) for r in rr);strict=sum(r['strict_entry'].get('valid',False) for r in rr);paired=[r for r in rr if r.get('_native_accounting_context',{}).get('paired_reference') and r['entry']['state']=='COMPLETE_NATIVE_SUPPORT'];known=[r for r in rr if 'break_even_eur' in r['entry']]
 stats=lambda v:{'n':len(v),'min':min(v) if v else None,'median':statistics.median(v) if v else None,'max':max(v) if v else None}
 manifest=[]
 original={r['sid']:r for r in st['original_statuses']}
 for sid,row in st['rows'].items():
  s=int(sid);rec=st['identity_records'].get(sid);manifest.append({'sid':s,'symbol':row['symbol'],'class':row['class'],'known_M5_at_acceptance':original[s]['known_accepted_M5'],'structural_eligible':original[s]['structural_eligible'],'state':rec['state'] if rec else 'FX_OR_CONTRACT_UNRESOLVED' if any('MISSING' in r or 'UNRESOLVED' in r for r in original[s]['structural_reasons']) else 'NOT_STRUCTURALLY_TRADABLE','exact_causes':rec.get('reason_counts',rec.get('cause')) if rec else original[s]['structural_reasons'],'intervals':rec.get('events',[]) if rec else []})
 state_counts=dict(Counter(r['state'] for r in manifest));qual=qualifying(rr);par=parity(db,st,tmp);summary={'schema':'mxm.full.native.frontier.final.summary.v1','source_head':store.head,'final_run':int(os.environ['GITHUB_RUN_ID']),'catalog':5326,'structural_eligible':len(st['eligible']),'completed_eligible':st['identity_cursor'],'all_required_work_completed':st['identity_cursor']==len(st['eligible']),'state_counts':state_counts,'relevant_domain':{'start_utc':'2026-08-24T00:00:00Z','end_exclusive_utc':'2026-09-14T00:00:00Z','warmup_start_utc':'2026-08-19T00:00:00Z','definition':'ALL_CURRENT_PROXY_NATIVE_SESSION_OPEN_PLUS20MIN_AND_MATCHED_PLUS120MIN;15MIN_EXITS;ALL_ELIGIBLE_IDS;COMPLETE_NATIVE_M5_INTERVAL','scope_limit':'NOT_EVERY_HISTORICAL_TICK_IN_ALL_TIME;REQUIRED_DOMAIN_AND_REMAINING_GAPS_ARE_EXPLICIT'},'global_archive':st['archive'],'new_requests':st['requests'],'original_report_preserved_sha256':a['original_report_sha256'],'quote_state_comparison':{'all_entry_clocks':len(rr),'strict5s_2s_supported':strict,'causal_expiry300s_supported':valid,'increased_causal_reference_support':valid-strict,'not_fill_guarantee':True,'future_quotes_used':False},'costs':{'entry_known':len(known),'paired_entry_exit_reference':len(paired),'exante_feasible':sum(r['entry'].get('eligible',False) for r in rr),'break_even_eur':stats([r['entry']['break_even_eur'] for r in known]),'break_even_bps':stats([r['entry']['break_even_bps'] for r in known]),'planned_risk_eur':stats([r['entry']['planned_risk_eur'] for r in known]),'actual_historical_financing_slippage_fills':None,'stop_guarantee':False,'constraints_fraction_equity':{'risk':.01,'margin':.4,'reserve':.6}},'79_pair_semantics':st['accounting_79_reconciliation'],'consecutive_weeks':{w:{'events':sum(r['iso']==w for r in rr),'cost_reference_feasible':sum(r['iso']==w and r['entry'].get('eligible',False) for r in rr),'paired_reference':sum(r['iso']==w for r in paired),'continuous_M5_not_continuous_quote_history':True} for w in ('2026-W35','2026-W36','2026-W37')},'candidate_qualification':qual,'candidate_review':st['candidate_review'],'pilot':st['pilot'],'parity_contract':par,'cold_resume_proofs':st['resume_proofs'],'uncertain_wire':st['uncertain_wire'],'errors':st['errors'],'HARD21':False,'alpha_certified':False,'protected_forward':False,'actual_orders':0,'actual_fills':0,'new_cloud_deployment':False,'firm_decision':'NO_PROMOTION;REQUIRED_NATIVE_DOMAIN_CLASSIFIED;PILOT_EXACT_RESULT_GOVERNS_ONLY_ITS_EXACT;CLOUD_FEED_AND_DISJOINT_CONFIRMATION_REMAIN_UNAUTHORIZED' if st['pilot'] else 'NO_QUALIFIED_NATIVE_PILOT_IN_REQUIRED_DOMAIN;COST_AND_SUPPORT_LIMITS_EXPLICIT;NO_GLOBAL_UNPROFITABILITY_CLAIM'}
 full={'summary':summary,'universe_manifest':manifest,'state_manifest':{k:v for k,v in st.items() if k not in ('catalog','rows','identity_records','pilot')}};meta=asset_value(store,full,'final-native-economic-frontier-owner.mxmenc');signer=serialization.load_pem_private_key(key.read_bytes(),password=None);raw=encode(summary);sig=signer.sign(raw,padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.MAX_LENGTH),hashes.SHA256());signer.public_key().verify(sig,raw,padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.MAX_LENGTH),hashes.SHA256());signed={'summary':summary,'summary_canonical_sha256':E.a.sha(raw),'owner_signature_b64':base64.b64encode(sig).decode(),'owner_spki_sha256':E.w.old.FP,'complete_primary':meta,'release_id':store.release['id']};signed_asset=asset_value(store,signed,'final-signed-owner-summary.mxmenc');relay=E.upload_extra(store.release,tmp,E.a.ROOT/(P+'RECIPIENT_PUBLIC_KEY.pem'),signed,'final-recipient-summary.mxmenc');safe={k:summary[k] for k in ('schema','source_head','catalog','structural_eligible','completed_eligible','all_required_work_completed','state_counts','new_requests','quote_state_comparison','consecutive_weeks','candidate_qualification','HARD21','alpha_certified','actual_orders','actual_fills','new_cloud_deployment','firm_decision')};safe.update(state='FINAL',generation=st['generation'],release_id=store.release['id'],full_primary=meta,signed_owner=signed_asset,recipient=relay,OWNER_READBACK_SUCCESS=True,DELIVERY_SUCCESS=False,global_archive_sources=len(st['archive']['asset_receipts']),cold_resume_count=len(st['resume_proofs']));update_body(store,safe)
 # Only encrypted full detail and safe metadata are Git artifacts.
 asset=E.w.old.api('releases/assets/'+str(relay['id']));cipher=E.w.old.download(asset['browser_download_url'],asset['size']);need(E.a.sha(cipher)==relay['ciphertext_sha256'],'FINAL_RECIPIENT_CIPHER');entries=[]
 for path,content in [(P+'FINAL_RECIPIENT_SUMMARY_V1.mxmenc.b64',base64.b64encode(cipher).decode()+'\n'),(P+'FINAL_PUBLIC_SAFE_V1.json',json.dumps(safe,sort_keys=True,indent=2)+'\n')]:
  blob=E.w.old.api('git/blobs',{'content':content,'encoding':'utf-8'});entries.append({'path':path,'mode':'100644','type':'blob','sha':blob['sha']})
 need(E.w.old.api('git/ref/heads/'+E.w.old.BRANCH)['object']['sha']==store.head,'FINAL_HEAD_DRIFT');tree=E.w.old.api('git/trees',{'base_tree':E.w.old.api('git/commits/'+store.head)['tree']['sha'],'tree':entries});commit=E.w.old.api('git/commits',{'message':'Preserve full classified native frontier and encrypted signed economic result [skip ci]','parents':[store.head],'tree':tree['sha']});E.w.old.api('git/refs/heads/'+E.w.old.BRANCH,{'sha':commit['sha'],'force':False},method='PATCH');safe['final_head']=commit['sha'];update_body(store,safe)


def main():
 global PHASE
 os.umask(0o077);head,a=gate()
 with tempfile.TemporaryDirectory(prefix='mxm-full-frontier-',dir=os.environ['RUNNER_TEMP']) as td:
  tmp=pathlib.Path(td);key,fp=E.w.old._private_key_from_secret(tmp);need(fp==E.w.old.FP,'OWNER_KEY');store=FrontierStore(head,key,E.a.ROOT/E.w.old.PUBLIC_KEY,tmp,'real');store.release=release_for(head,a);body=json.loads(store.release['body']);db=ar.dbopen(tmp/'native.sqlite')
  if body.get('state')=='FINAL':
   pathlib.Path(os.environ['GITHUB_OUTPUT']).open('a').write('done=true\n');print('ALREADY_FINAL_NO_BROKER');return
  if os.environ['GITHUB_JOB']=='bootstrap':
   need('current_journal' not in body,'BOOTSTRAP_ALREADY_PRESERVED');bootstrap(db,store,a,tmp,key);pathlib.Path(os.environ['GITHUB_OUTPUT']).open('a').write('done=false\n');return
  st=restore(db,store);st['campaign_tick_cap']=a['campaign_max_tick_requests'];st['rows']={str(s):r for s,r in st['rows'].items()};st['phase']='RUNNING_NATIVE_WORK';deadline=time.monotonic()+a['worker_capture_seconds'];col=Collector({'BID_ASK':a['campaign_max_tick_requests'],'M5':a['campaign_max_m5_requests']});PHASE='AUTHENTIC_NATIVE_WORK'
  try:
   col.connect();need(col.aid==int(st['catalog']['trader']['ctidTraderAccountId']),'SAME_ACCEPTED_ACCOUNT')
   while st['identity_cursor']<len(st['eligible']) and time.monotonic()<deadline:
    sid=st['eligible'][st['identity_cursor']]
    complete=process_identity(db,sid,st,col,store,a,deadline)
    if not complete:break
    st['identity_cursor']+=1;st.setdefault('_record_dirty',set()).add(sid%64)
    if st['identity_cursor']%8==0 or st['identity_cursor']==len(st['eligible']):
     pilot(db,st,store,a);persist(db,store,st,'identity-'+str(st['identity_cursor']))
    need(st['requests']['M5']<=a['campaign_max_m5_requests'],'FINITE_M5_CAP')
  except Exception as ex:
   code=str(ex) if re.fullmatch('[A-Z0-9_]{1,100}',str(ex)) else type(ex).__name__;st['errors'].append({'run':int(os.environ['GITHUB_RUN_ID']),'job':os.environ['GITHUB_JOB'],'cause':code,'phase':PHASE});st['phase']='RECOVERABLE_INTERRUPTION_OR_EXPLICIT_LIMIT';print('DURABLE_FRONTIER_INTERRUPTION_'+code,flush=True)
  finally:col.close();persist(db,store,st,'worker-end')
  if st['identity_cursor']==len(st['eligible']):
   PHASE='FINAL_CAUSAL_PARITY_AND_ECONOMIC_REPORT';pilot(db,st,store,a);final_report(db,st,store,a,tmp,key);pathlib.Path(os.environ['GITHUB_OUTPUT']).open('a').write('done=true\n')
  else:pathlib.Path(os.environ['GITHUB_OUTPUT']).open('a').write('done=false\n')
if __name__=='__main__':
 try:main()
 except Exception as ex:
  code=str(ex) if re.fullmatch('[A-Z0-9_]{1,100}',str(ex)) else type(ex).__name__;print('FAIL_CLOSED_FULL_FRONTIER_'+PHASE+'_'+code,flush=True)
  if PHASE=='GATE' and 'GITHUB_OUTPUT' in os.environ:pathlib.Path(os.environ['GITHUB_OUTPUT']).open('a').write('done=true\n')
  raise SystemExit(1) from None
