"""One frozen no-contact economic DEVELOPMENT pilot, original source guards intact."""
import os,json,gzip,subprocess,pathlib,tempfile,hashlib,math
from collections import defaultdict,Counter
from datetime import datetime,timedelta,timezone
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.quote_path_recipient_recovery_20261013_v1 import delivery_contract_v1 as custody
from research_core_v4.numeric_development_v1.public_output_guard_v1 import validate_public_blob,ROOT as PUBLIC_ROOT
from research_core_v4.multiscale_regime_v1.cost_universe_v1 import class_product
from competition.broker_universe_capture import entry_eligibility
from research_core_v4.cost_frequency_discovery_v1 import accounts_v1 as fx
from . import kernel_v1 as k,economics_v1 as econ
e=rt.e;P='research_core_v4/factor_loading_drift_20261014_v1/';WF='.github/workflows/mxm-factor-loading-drift-20261014-v1.yml';PHASE='GATE'
def need(v,c):e.w.old.need(bool(v),c)
def when(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
def gate():
 head=os.environ['GITHUB_SHA'];e.w.v2.runtime(head);a=json.loads((e.a.ROOT/(P+'EXECUTION_V1.json')).read_text())
 need(a['authority']=='EXPLICIT_OWNER_FACTOR_NET_RESEARCH_20261014','OWNER_SCOPE');need(not any(a[n] for n in ('orders','protected_forward','cloud_deployment','new_broker_requests','closed_exact_replay')),'SCOPE')
 need(os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/'+WF+'@refs/heads/'+e.w.old.BRANCH,'WORKFLOW')
 need(datetime.now(timezone.utc)<when(a['expires_utc']),'EXPIRED')
 for path,digest in a['bindings'].items():need(e.w.old.filehash(path)==digest,'SOURCE_BINDING')
 public=(e.a.ROOT/(P+'RECIPIENT_PUBLIC_KEY.pem')).read_bytes();ready=json.loads((e.a.ROOT/(P+'RECIPIENT_READY_V1.json')).read_text())
 need(custody.fingerprint(public)==a['recipient_spki_sha256'],'RECIPIENT_KEY');custody.require_ready(ready,public,a['invocation_id'],when(a['expires_utc']))
 e.a.ancestor(a['base_head'],head);old=set(subprocess.check_output(['git','ls-tree','-r',a['base_head']],cwd=e.a.ROOT,text=True).splitlines());new=set(subprocess.check_output(['git','ls-tree','-r',head],cwd=e.a.ROOT,text=True).splitlines());need(old<=new,'OLD_FILES_UNCHANGED')
 master,entries,digits,manifest=e.w.old.verify_science();need(not e.w.v2.existing_ref(a['one_use_ref']),'ONE_USE');e.w.old.api('git/refs',{'ref':'refs/tags/'+a['one_use_ref'],'sha':head});return head,a,master,entries,digits,manifest

def qualify(source,master):
 cat=source['catalog'];rows={int(r['sid']):dict(r) for r in source['identities']};light={int(z['symbolId']):z for z in cat['light']};eligible={};status=[]
 fields=('commissionType','preciseTradingCommissionRate','preciseMinCommission','minCommissionType','pnlConversionFeeRate')
 for sid,row in sorted(rows.items()):
  f=cat['full'].get(str(sid));why=[]
  if f is None or sid not in light:why.append('NO_NATIVE_FULL_CONTRACT')
  else:
   buy,sell=entry_eligibility(light[sid],f)
   if buy is not True or sell is not True:why.append('NOT_BOTH_NATIVE_ENTRY_DIRECTIONS')
   if any(name not in f for name in fields):why.append('NATIVE_FEE_FIELDS_UNRESOLVED')
   try:
    minv=int(f['minVolume']);step=int(f['stepVolume']);lot=int(f['lotSize'])
    if minv<=0 or step<=0 or lot<=0 or minv>int(f['maxVolume']) or minv%step:why.append('NATIVE_VOLUME_LATTICE')
    margin=float(row['margin_eur'])
    if not math.isfinite(margin) or margin<=0 or margin>80:why.append('MINIMUM_MARGIN_GT80_OR_UNKNOWN')
   except (ValueError,KeyError,TypeError):why.append('NATIVE_VOLUME_MARGIN_MISSING')
   typ=class_product(row['symbol'],row['class'])
   if typ=='OTHER_OR_TEST_CFD':why.append('UNRESOLVED_OR_TEST_PRODUCT')
   if not row['quote'] or not f.get('scheduleTimeZone'):why.append('COHORT_CURRENCY_OR_TIMEZONE_MISSING')
   if not why:
    row.update(min_units=minv/100,margin_eur=margin,product_type=typ)
    row['factor_group']='|'.join([row['class'],row['quote'],typ,f['scheduleTimeZone']]);eligible[sid]=row
  status.append({'sid':sid,'structural_eligible':not why,'reasons':why,'accepted_M5':sid in {m['symbol_id'] for m in master}})
 return cat,rows,eligible,status

def corpus(key,fp,tmp,master,entries,digits,manifest):
 rel=e.w.old.api('releases/tags/'+manifest['DURABLE_RELEASE_IDENTITY']);assets={z['name']:z for z in e.w.old.api('releases/'+str(rel['id'])+'/assets?per_page=100')};panel={};provenance=[];total=0
 for shard in range(25):
  buffers={i:{} for i in range(shard*64+1,min(1576,shard*64+64)+1)}
  for segment in range(1,5):
   entry=entries[(segment-1)*25+shard];asset=assets[entry['ENCRYPTED_ASSET_NAME']];need(asset['digest']=='sha256:'+entry['ENCRYPTED_ASSET_SHA256'],'SHARD_NATIVE_DIGEST')
   blob=e.w.old.download(asset['browser_download_url'],asset['size']);need(e.a.sha(blob)==entry['ENCRYPTED_ASSET_SHA256'],'SHARD_CIPHER');raw=e.w.old.crypto.decrypt_package(blob,private_key=key,expected_public_spki_sha256=fp,temp_parent=tmp);need(e.a.sha(raw)==entry['PLAINTEXT_CANONICAL_SHA256'],'SHARD_PLAINTEXT')
   obj=e.w.n.canonical.strict_json(raw);need(e.w.n.canonical.canonical(obj)==raw and set(obj)==e.w.n.canonical.PACKAGE_KEYS and obj['segment_index']==segment and obj['shard_index']==shard and obj['identity_range']==entry['IDENTITY_RANGE'],'SHARD_CONTRACT')
   lo,hi=entry['IDENTITY_RANGE'];need(len(obj['items'])==hi-lo+1,'SHARD_ROSTER');count=0
   for ordinal,item in zip(range(lo,hi+1),obj['items']):
    need(item['ordinal']==ordinal and item['symbol_id']==master[ordinal-1]['symbol_id'] and item['failure'] is None,'SOURCE_NATIVE_IDENTITY');last=-1
    for row in item['rows']:
     t,bar=e.w.n._bar(row,digits[item['symbol_id']]);need(t>last and t not in buffers[ordinal] and (t-k.START)//604800==segment-1,'SOURCE_CHRONOLOGY');last=t;buffers[ordinal][t]=bar;count+=1
   need(count==entry['ROW_COUNT'] and entry['PROTECTED_FORWARD_ROW_COUNT']==0,'SOURCE_COUNT');total+=count;provenance.append({'asset_id':asset['id'],'segment':segment,'shard':shard,'ciphertext_sha256':entry['ENCRYPTED_ASSET_SHA256'],'canonical_sha256':entry['PLAINTEXT_CANONICAL_SHA256'],'rows':count})
  for ordinal,bars in buffers.items():panel[master[ordinal-1]['symbol_id']]=k.reduce(bars)
  del buffers;print(json.dumps({'phase':'AUTHENTIC_SOURCE_REDUCTION','shard_groups_complete':shard+1,'private_market_vectors':False}),flush=True);e.w.old.budget(maxwall=2400,maxcpu=1800,maxkib=3145728)
 need(total==3355389 and len(panel)==1576 and len(provenance)==100,'FULL_ACCEPTED_CORPUS');return panel,provenance,total

def publish(head,a,tmp,key,summary,records,provenance):
 status_path=PUBLIC_ROOT+'OWNER_FACTOR_LOADING_DRIFT_V1.json';status={'schema':e.w.SCHEMA,'source_head':head,'phase':'PUBLICATION','status':'NOT_PERSISTED','failure_code':'NONE','run_id':int(os.environ['GITHUB_RUN_ID'])}
 store=e.w.old.GitHubStore(head,key,e.a.ROOT/e.w.old.PUBLIC_KEY,tmp,'real');store.release=e.w.old.api('releases',{'tag_name':'mxm-factor-loading-drift-'+a['invocation_id']+'-'+os.environ['GITHUB_RUN_ID'],'target_commitish':head,'name':'MXM encrypted factor loading drift economic DEVELOPMENT','prerelease':True,'body':validate_public_blob(status_path,status).decode()})
 chunks=[]
 for i in range(0,len(records),5000):
  value=e.w.old.crypto.strict_json(e.a.enc({'schema':'mxm.factor.loading.private.trade.chunk.v1','source_head':head,'offset':i,'records':records[i:i+5000]}));chunks.append(store.encrypted(value,'factor-loading-records-'+str(i//5000)+'.mxmenc'))
 summary.update(source_head=head,run_id=int(os.environ['GITHUB_RUN_ID']),record_count=len(records),durable_trade_chunks=chunks)
 full=e.w.old.crypto.strict_json(e.a.enc({'summary':summary,'input_provenance':provenance,'design':json.loads((e.a.ROOT/(P+'DESIGN_V1.json')).read_text())}));primary=store.encrypted(full,'factor-loading-owner-result.mxmenc')
 loaded,proof=load_asset(key,e.w.old.FP,tmp,{'release_id':store.release['id'],'asset_id':primary['id'],'ciphertext_sha256':primary['ciphertext_sha256']});need(loaded==full,'OWNER_VERIFIED_PARITY')
 s=loaded['summary'];envelope={'schema':'mxm.factor.loading.verified.summary.v1','summary':s,'summary_canonical_sha256':e.a.sha(e.a.enc(s)),'original_primary':proof,'source_head':head,'source_run':int(os.environ['GITHUB_RUN_ID']),'recipient_spki_sha256':a['recipient_spki_sha256'],'OWNER_READBACK_SUCCESS':True,'NUMERIC_SUCCESS':True,'numeric_kind':'EXPLORATORY_ECONOMIC_PILOT_NOT_CONFIRMATION','DELIVERY_SUCCESS':False}
 delivered=e.upload_extra(store.release,tmp,e.a.ROOT/(P+'RECIPIENT_PUBLIC_KEY.pem'),envelope,'factor-loading-recipient-summary.mxmenc')
 store.encrypted({'primary':proof,'relay':delivered,'summary_sha256':envelope['summary_canonical_sha256'],'OWNER_READBACK_SUCCESS':True,'recipient_readback_verified':False},'factor-loading-attestation.mxmenc')
 status.update(phase='FINAL',status='PASS',encrypted_artifact_name=delivered['name'],encrypted_artifact_sha256=delivered['ciphertext_sha256']);body=validate_public_blob(status_path,status);e.w.old.api('releases/'+str(store.release['id']),{'body':body.decode()},method='PATCH');need(e.w.old.api('releases/'+str(store.release['id']))['body'].encode()==body,'PUBLIC_RECEIPT')
 e.w.old.api('git/refs',{'ref':'refs/tags/'+a['owner_complete_ref'],'sha':head});print(body.decode().strip(),flush=True)

def main():
 global PHASE
 os.umask(0o077);head,a,master,entries,digits,manifest=gate()
 with tempfile.TemporaryDirectory(prefix='mxm-factor-loading-',dir=os.environ['RUNNER_TEMP']) as td:
  tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'OWNER_KEY');test=e.a.enc({'synthetic_only':True,'invocation':a['invocation_id']});testpath=tmp/'test.mxmenc';e.w.old.encrypt_shard(test,public_key=e.a.ROOT/e.w.old.PUBLIC_KEY,output=testpath);need(e.w.old.crypto.decrypt_package(testpath.read_bytes(),private_key=key,expected_public_spki_sha256=fp,temp_parent=tmp)==test,'PREPRICE_OWNER_CRYPTO_TEST')
  PHASE='FROZEN_UNIVERSE_AND_CATALOG';source,catproof=load_asset(key,fp,tmp,a['catalog_source']);cat,allrows,eligible,status=qualify(source,master)
  graph=fx.graph(list(allrows.values()));groups=defaultdict(list)
  for sid,row in sorted(eligible.items()):
   if sid in {m['symbol_id'] for m in master}:groups[row['factor_group']].append(sid)
  rosters={g:ids for g,ids in sorted(groups.items())};membership_sha=e.a.sha(e.a.enc(rosters))
  # Save no outcome-derived selection. CURRENT metadata is not historical membership authority.
  PHASE='AUTHENTIC_ACCEPTED_M5';panel,provenance,rowcount=corpus(key,fp,tmp,master,entries,digits,manifest)
  PHASE='EXISTING_NATIVE_QUOTE_INTERSECTION';cost,costproof=load_asset(key,fp,tmp,a['fullcost_source']);quotes={(int(q['symbol_id']),int(q['boundary_ms'])//1000):q for q in cost['private_boundary_receipts']};del cost
  PHASE='ONE_LOADING_DRIFT_PILOT';factor,coverage=k.factors(panel,rosters);trials=[];identity=[]
  for sid in sorted(factor):
   vv,reasons=k.forecasts(sid,panel[sid],factor[sid]);trials.extend(vv);identity.append({'sid':sid,'class':eligible[sid]['class'],'factor_group':eligible[sid]['factor_group'],'reasons':reasons,'metrics':k.metrics(vv),'blocks':[k.metrics([z for z in vv if z['block']==b]) for b in range(4)]})
  records=[];entry_counts=Counter()
  for ev in trials:
   row=eligible[ev['sid']];f=cat['full'][str(row['sid'])];en=econ.planned(ev,row,f,panel,graph);entry_counts[en['reason']]+=1;scenarios={}
   for scenario in econ.SCENARIOS:
    model=econ.account(ev,k.sign(ev['model']),row,f,panel,graph,scenario);base=econ.account(ev,k.sign(ev['baseline']),row,f,panel,graph,scenario)
    scenarios[scenario]={'model':model,'baseline':base} if model is not None and base is not None else None
   q1=econ.exact(ev,k.sign(ev['model']),row,f,quotes,graph,panel);q0=econ.exact(ev,k.sign(ev['baseline']),row,f,quotes,graph,panel)
   records.append({**ev,'entry':en,'scenarios':scenarios,'exact':{'model':q1,'baseline':q0} if q1 is not None and q0 is not None else None})
  summary={'schema':'mxm.factor.loading.economic.summary.v1','classification':'DEVELOPMENT_ADAPTIVE_EXPLORATORY','mechanism':'CAUSAL_FACTOR_LOADING_DRIFT_ADJUSTMENT','broker_catalog':len(allrows),'current_minimum_margin_le80_eligible':len(eligible),'eligible_with_accepted_M5':sum(s in panel for s in eligible),'accepted_master':1576,'authenticated_shards':100,'authenticated_rows':rowcount,'all_catalog_identity_status':status,'factor_membership_sha256':membership_sha,'factor_memberships':rosters,'factor_support':coverage,'identity_support':identity,'gross':k.metrics(trials),'gross_blocks':[k.metrics([x for x in trials if x['block']==b]) for b in range(4)],'gross_by_class':{c:k.metrics([x for x in trials if eligible[x['sid']]['class']==c]) for c in sorted({r['class'] for r in eligible.values()})},'economic_all_single_leg_opportunities':econ.totals(records),'economic_admitted_single_leg_opportunities':econ.totals(records,'eligible'),'economic_blocks':[econ.totals([r for r in records if r['block']==b],'eligible') for b in range(4)],'economic_iso_utc':{w:econ.totals([r for r in records if r['iso']==w],'eligible') for w in sorted({r['iso'] for r in records})},'one_position_portfolio_proxy':econ.portfolio(records),'entry_reasons':dict(entry_counts),'cost_provenance':[catproof,costproof],'existing_native_quote_boundaries':len(quotes),'new_broker_requests':0,'old_predictive_or_exit_kernel_calls':0,'orders':0,'protected_forward':False,'cloud_deployment':False,'alpha_claimed':False,'NET_positive_certified':False,'HARD21':'NOT_DEMONSTRATED','cohort_authority':'PROSPECTIVELY_DEFINED_STATISTICAL_COHORT_OPERATOR_USING_ACCEPTED_CURRENT_METADATA;NOT_OFFICIAL_INDEX_HOLDINGS_OR_HISTORIC_MEMBERSHIP','historical_current_terms_difference':'CURRENT_MIN_VOLUME_MARGIN_FEES_SCHEDULES_NOT_CERTIFIED_POINT_IN_TIME_AUG_SEP;ALL_NET_CURRENT_TERMS_SCENARIOS_OR_PROXY','inference':'NO_PVALUE_OR_INDEPENDENT_TRIAL_CLAIM;4_OVERLAPPING_DEVELOPMENT_TIME_BLOCKS_CROSS_SYMBOL_DEPENDENCE_PRIOR_SELECTION_EXPOSURE','semantic_scope':'NEW_EXACT_STATISTICAL_LOADING_DRIFT_CONSTRUCTOR;OLD_FACTOR_BASKET_V3_REQUIRING_HISTORICAL_CONSTITUENT_AUTHORITY_UNCHANGED_NOT_CERTIFIED','budget':e.w.old.usage()}
  summary['verdict']='PILOT_COMPLETED_NO_EXECUTABLE_NET_EDGE_CERTIFICATION'
  PHASE='DURABLE_OWNER_AND_RECIPIENT_DELIVERY';publish(head,a,tmp,key,summary,records,provenance)
if __name__=='__main__':
 try:main()
 except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(1)
