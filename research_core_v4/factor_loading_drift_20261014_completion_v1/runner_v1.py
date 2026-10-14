"""Finish currency valuation of saved forecasts. No fit or new scientific pilot."""
import os,json,math,pathlib,tempfile,subprocess
from collections import Counter
from decimal import Decimal
from datetime import datetime,timezone
from research_core_v4.factor_loading_drift_20261014_v1 import runner_v1 as saved
from research_core_v4.factor_loading_drift_20261014_v1 import economics_v1 as econ
from research_core_v4.factor_loading_drift_20261014_v1 import kernel_v1 as k
from research_core_v4.native_executable_qualification_v1.runner_v1 import rowcheck
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.cost_frequency_discovery_v1 import accounts_v1 as fx
from research_core_v4.quote_path_recipient_recovery_20261013_v1 import delivery_contract_v1 as custody
e=saved.e;rt=saved.rt;P='research_core_v4/factor_loading_drift_20261014_completion_v1/';WF='.github/workflows/mxm-factor-loading-economic-completion-20261014-v1.yml';PHASE='GATE'
def need(v,c):e.w.old.need(bool(v),c)
def project_native(rows,sid,digits):
 out={}
 for key,row in rows.items():
  # Accepted integrated-history producer stores [open,high,low,close,tick_volume].
  if isinstance(row,list):
   need(len(row)==5,'ACCEPTED_NATIVE_VECTOR_SCHEMA')
   row={'time_utc':datetime.fromtimestamp(int(key),timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),**dict(zip(('open','high','low','close','tick_volume'),row))}
  need(isinstance(row,dict),'ACCEPTED_NATIVE_ROW_SCHEMA')
  t=rowcheck(row);need(t==int(key),'ACCEPTED_NATIVE_TIMESTAMP_BINDING')
  if not k.START<=t<k.END:continue
  projected={'time_utc':row['time_utc'],'tick_volume':str(int(float(row['tick_volume'])))}
  for name in ('open','high','low','close'):
   value=Decimal(str(row[name]));need(value==value.quantize(Decimal(1).scaleb(-digits)),'NATIVE_DIGITS_NO_PRICE_CHANGE');projected[name]=format(value,f'.{digits}f')
  t2,bar=e.w.n._bar(projected,digits);need(t2==t,'UNCHANGED_M5_DOMAIN_GUARD');out[t]=bar
 return out

def gate():
 h=os.environ['GITHUB_SHA'];e.w.v2.runtime(h);a=json.loads((e.a.ROOT/(P+'EXECUTION_V1.json')).read_text());need(a['authority']=='OWNER_EXISTING_FACTOR_PILOT_ECONOMIC_COMPLETION_20261014','OWNER_SCOPE');need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1' and os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/'+WF+'@refs/heads/'+e.w.old.BRANCH,'WORKFLOW');need(not any(a[n] for n in ('orders','protected_forward','new_broker_requests','new_forecasts','parameter_changes')),'SCOPE');need(datetime.now(timezone.utc)<saved.when(a['expires_utc']),'EXPIRED')
 for p,hsh in a['bindings'].items():need(e.w.old.filehash(p)==hsh,'SOURCE_BINDING')
 e.a.ancestor(a['base_head'],h);old=set(subprocess.check_output(['git','ls-tree','-r',a['base_head']],cwd=e.a.ROOT,text=True).splitlines());new=set(subprocess.check_output(['git','ls-tree','-r',h],cwd=e.a.ROOT,text=True).splitlines());need(old<=new,'ALL_PRIOR_FILES_UNCHANGED')
 ready=json.loads((e.a.ROOT/(P+'RECIPIENT_READY_V1.json')).read_text());public=(e.a.ROOT/'research_core_v4/factor_loading_drift_20261014_v1/RECIPIENT_PUBLIC_KEY.pem').read_bytes();custody.require_ready(ready,public,a['invocation_id'],saved.when(a['expires_utc']));need(custody.fingerprint(public)==a['recipient_spki_sha256'],'RECIPIENT');need(not e.w.v2.existing_ref(a['one_use_ref']),'ONE_USE');e.w.old.api('git/refs',{'ref':'refs/tags/'+a['one_use_ref'],'sha':h});return h,a,e.w.old.verify_science()

def publish(head,a,tmp,key,full,records):
 from research_core_v4.numeric_development_v1.public_output_guard_v1 import validate_public_blob,ROOT as PUB
 path=PUB+'OWNER_FACTOR_ECONOMIC_COMPLETION_V1.json';status={'schema':e.w.SCHEMA,'source_head':head,'phase':'PUBLICATION','status':'NOT_PERSISTED','failure_code':'NONE','run_id':int(os.environ['GITHUB_RUN_ID'])}
 store=e.w.old.GitHubStore(head,key,e.a.ROOT/e.w.old.PUBLIC_KEY,tmp,'real');store.release=e.w.old.api('releases',{'tag_name':'mxm-factor-economic-completion-'+a['invocation_id']+'-'+os.environ['GITHUB_RUN_ID'],'target_commitish':head,'name':'MXM encrypted existing factor forecast economic completion','prerelease':True,'body':validate_public_blob(path,status).decode()});chunks=[]
 for i in range(0,len(records),5000):chunks.append(store.encrypted(e.w.old.crypto.strict_json(e.a.enc({'offset':i,'records':records[i:i+5000]})),'completed-records-'+str(i//5000)+'.mxmenc'))
 full['summary'].update(source_head=head,run_id=int(os.environ['GITHUB_RUN_ID']),durable_economic_chunks=chunks);full=e.w.old.crypto.strict_json(e.a.enc(full));primary=store.encrypted(full,'factor-economic-owner-result.mxmenc');loaded,proof=load_asset(key,e.w.old.FP,tmp,{'release_id':store.release['id'],'asset_id':primary['id'],'ciphertext_sha256':primary['ciphertext_sha256']});need(loaded==full,'OWNER_PARITY');s=loaded['summary']
 envelope={'schema':'mxm.factor.economic.completed.verified.summary.v1','summary':s,'summary_canonical_sha256':e.a.sha(e.a.enc(s)),'original_primary':proof,'source_head':head,'source_run':int(os.environ['GITHUB_RUN_ID']),'recipient_spki_sha256':a['recipient_spki_sha256'],'OWNER_READBACK_SUCCESS':True,'NUMERIC_SUCCESS':True,'numeric_kind':'SAVED_FORECAST_ECONOMIC_COMPLETION_NO_REFIT','DELIVERY_SUCCESS':False}
 relay=e.upload_extra(store.release,tmp,e.a.ROOT/'research_core_v4/factor_loading_drift_20261014_v1/RECIPIENT_PUBLIC_KEY.pem',envelope,'factor-economic-recipient-summary.mxmenc');store.encrypted({'primary':proof,'relay':relay,'summary_sha256':envelope['summary_canonical_sha256'],'OWNER_READBACK_SUCCESS':True,'recipient_readback_verified':False},'factor-economic-attestation.mxmenc');status.update(phase='FINAL',status='PASS',encrypted_artifact_name=relay['name'],encrypted_artifact_sha256=relay['ciphertext_sha256']);body=validate_public_blob(path,status);e.w.old.api('releases/'+str(store.release['id']),{'body':body.decode()},method='PATCH');need(e.w.old.api('releases/'+str(store.release['id']))['body'].encode()==body,'PUBLIC_READBACK');e.w.old.api('git/refs',{'ref':'refs/tags/'+a['owner_complete_ref'],'sha':head});print(body.decode().strip(),flush=True)

def main():
 global PHASE
 os.umask(0o077);head,a,(master,entries,digits,manifest)=gate()
 with tempfile.TemporaryDirectory(prefix='mxm-factor-economic-completion-',dir=os.environ['RUNNER_TEMP']) as td:
  tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'OWNER_KEY');PHASE='RECOVER_SAVED_FORECASTS';original,proof=load_asset(key,fp,tmp,a['original_primary']);s=original['summary'];need(s['source_head']==a['original_head'] and s['run_id']==38513586733,'ORIGINAL_PILOT_BINDING')
  records=[];recordproof=[]
  for chunk in s['durable_trade_chunks']:
   obj,cp=load_asset(key,fp,tmp,{'release_id':a['original_primary']['release_id'],'asset_id':chunk['id'],'ciphertext_sha256':chunk['ciphertext_sha256'],'canonical_sha256':chunk['canonical_sha256']});need(obj['offset']==len(records) and obj['source_head']==a['original_head'],'SAVED_RECORD_SEQUENCE');records.extend(obj['records']);recordproof.append(cp)
  need(len(records)==s['record_count']==27971,'SAVED_FORECAST_COUNT');forecast_fields=('sid','j','t','exit','block','iso','model','baseline','loading_fast','loading_slow','factor','new_feature','y','atr_price','train_n');forecast_sha=e.a.sha(e.a.enc([{n:r[n] for n in forecast_fields} for r in records]))
  PHASE='ACCEPTED_INPUT_VALUATION_ONLY';cat_source,catproof=load_asset(key,fp,tmp,a['catalog_source']);cat,allrows,eligible,_=saved.qualify(cat_source,master);graph=fx.graph(list(allrows.values()));panel,provenance,rowcount=saved.corpus(key,fp,tmp,master,entries,digits,manifest)
  native,nativeproof=load_asset(key,fp,tmp,a['native_history_source']);extra=[]
  for sid_text,bars in native['bars'].items():
   sid=int(sid_text)
   if sid in panel:continue
   dd=int(cat['full'][str(sid)]['digits']);vv=project_native(bars,sid,dd);panel[sid]=k.reduce(vv);extra.append({'sid':sid,'source_rows_in_domain':len(vv),'role':'FX_VALUATION_CONTEXT_ONLY_NO_PREDICTOR_TARGET_OR_COHORT_CHANGE'})
  oldcost,costproof=load_asset(key,fp,tmp,a['fullcost_source']);quotes={(int(q['symbol_id']),int(q['boundary_ms'])//1000):q for q in oldcost['private_boundary_receipts']};del oldcost
  accepted_quotes,accepted_quote_proof=load_asset(key,fp,tmp,a['accepted_native_quote_source']);native_quote_added=0
  for q in accepted_quotes['private_quote_receipts']:
   key_quote=(int(q['symbol_id']),int(q['boundary_ms'])//1000)
   if key_quote not in quotes:quotes[key_quote]=q;native_quote_added+=1
  del accepted_quotes
  PHASE='FINISH_UNCHANGED_ECONOMIC_POLICY';completed=[]
  for r in records:
   ev={n:r[n] for n in forecast_fields};row=eligible[ev['sid']];f=cat['full'][str(row['sid'])];en=econ.planned(ev,row,f,panel,graph);scenarios={}
   for name in econ.SCENARIOS:
    one=econ.account(ev,k.sign(ev['model']),row,f,panel,graph,name);base=econ.account(ev,k.sign(ev['baseline']),row,f,panel,graph,name);scenarios[name]={'model':one,'baseline':base} if one is not None and base is not None else None
   one=econ.exact(ev,k.sign(ev['model']),row,f,quotes,graph,panel);base=econ.exact(ev,k.sign(ev['baseline']),row,f,quotes,graph,panel);completed.append({**ev,'entry':en,'scenarios':scenarios,'exact':{'model':one,'baseline':base} if one is not None and base is not None else None})
  need(e.a.sha(e.a.enc([{n:r[n] for n in forecast_fields} for r in completed]))==forecast_sha,'FORECAST_DIRECTION_LABEL_ATR_CHANGE')
  summary={'schema':'mxm.saved.factor.forecast.completed.economics.v1','original_pilot_head':a['original_head'],'original_pilot_run':38513586733,'original_primary':proof,'saved_forecast_count':len(completed),'saved_forecast_projection_sha256':forecast_sha,'forecasts_and_directions_byte_unchanged':True,'new_predictor_fits':0,'new_model_forecasts':0,'new_broker_requests':0,'original_gross':s['gross'],'original_gross_blocks':s['gross_blocks'],'universe':{n:s[n] for n in ('broker_catalog','current_minimum_margin_le80_eligible','eligible_with_accepted_M5','authenticated_rows','authenticated_shards')},'extra_accepted_native_context':extra,'native_history_proof':nativeproof,'economic_all_single_leg_opportunities':econ.totals(completed),'economic_admitted_single_leg_opportunities':econ.totals(completed,'eligible'),'economic_blocks':[econ.totals([r for r in completed if r['block']==b],'eligible') for b in range(4)],'economic_iso_utc':{w:econ.totals([r for r in completed if r['iso']==w],'eligible') for w in sorted({r['iso'] for r in completed})},'entry_reasons':dict(Counter(r['entry']['reason'] for r in completed)),'one_position_portfolio_proxy':econ.portfolio(completed),'cost_provenance':[catproof,costproof,nativeproof,accepted_quote_proof],'added_existing_native_quote_boundaries':native_quote_added,'record_provenance':recordproof,'policy_sha256':e.w.old.filehash('research_core_v4/factor_loading_drift_20261014_v1/DESIGN_V1.json'),'original_economics_code_sha256':e.w.old.filehash('research_core_v4/factor_loading_drift_20261014_v1/economics_v1.py'),'all_previous_files_unchanged':True,'alpha_claimed':False,'NET_positive_certified':False,'HARD21':'NOT_DEMONSTRATED','orders':0,'protected_forward':False,'cloud_deployment':False,'limits':'CURRENT_CAPTURED_TERMS_NOT_HISTORICAL_CHARGES;M5_FIXED_FRICTION_FX_STOP_TIMING_PROXY;NATIVE_QUOTE_COMPLETE_MATCH_ONLY;NO_PVALUE_OR_INDEPENDENT_CONFIRMATION'}
  summary['verdict']='UNCHANGED_PILOT_ECONOMIC_COMPLETION_NO_PROMOTION'
  PHASE='VERIFIED_OWNER_AND_RECIPIENT_DELIVERY';publish(head,a,tmp,key,{'summary':summary,'input_provenance':provenance},completed)
if __name__=='__main__':
 try:main()
 except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(1)
