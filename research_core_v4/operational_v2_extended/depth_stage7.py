"""One exact next support-only block. No real learner, prediction or loss route."""
import argparse,gzip,hashlib,json,os,pathlib,time,urllib.request
from datetime import datetime,timezone
import numpy as np
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/'research_core_v4/operational_v2'))
from bank import R,S,P,C,canonical,sha
from preflight import frozen,software
from provider import REPO,BRANCH,api,put
from research_core_v4.operational_v2_extended.power_stage7 import run_power
from masks import derive,ROSTER
CALENDAR='research_core_v4/state/STRICT_PREOUTCOME_OPERATIONAL_V2_EXTENDED_STAGE7_SUPPORT_CALENDAR_V1.json'
def epoch(s):return int(datetime.fromisoformat(s.replace('Z','+00:00')).timestamp())
def durable(path,head):
 assert path.startswith('support_depth_v2/') and not path.endswith('.mxmenc')
 return urllib.request.urlopen('https://raw.githubusercontent.com/'+REPO+'/'+head+'/'+path,timeout=90).read()
def counters(ledger):
 return {'all_wire_request_attempts':len(ledger),'history_request_attempts':sum(x['payload_type']==2137 for x in ledger),'send_returned_requests':sum(x['send_returned'] for x in ledger),'server_responses_bound':sum('response_sha256' in x for x in ledger),'raw_rows_streamed':sum(x.get('response_geometry',{}).get('raw_response_count',0) for x in ledger),'canonical_rows_streamed':sum(x.get('response_geometry',{}).get('canonical_inside_count',0) for x in ledger),'lower_overfetch_discarded':sum(x.get('response_geometry',{}).get('lower_overfetch_count',0) for x in ledger)}
def main(stage):
 from research_core_v4.operational_v2_extended.gate_stage7 import check,A,F
 check();f=frozen();software();assert stage==7
 authority=json.loads((R/A).read_bytes())
 head=api('/repos/'+REPO+'/git/ref/heads/'+BRANCH)['object']['sha'];assert head==authority['durable_base_head'],'DURABLE_BASE_DRIFT'
 pre=json.loads(durable('support_depth_v2/preflight.json',head));assert pre['status']=='PASS' and pre['broker_requests']==0
 calendar=json.loads((R/CALENDAR).read_bytes());block=calendar['blocks'][stage-1];start=epoch(block['from_utc']);end=epoch(block['end_exclusive_utc']);assert end-start==28*86400
 initial=gzip.decompress(durable('support_depth_v2/initial/validity.bin.gz',head));assert hashlib.sha256(initial).hexdigest()==pre['initial_validity_sha256'];pieces=[np.frombuffer(initial,np.uint8).reshape(1575,8064)];initial=None
 for oldstage in range(1,stage):
  result=json.loads(durable(f'support_depth_v2/stage{oldstage}/power.json',head));assert not result['shared_ready'],'NO_REQUEST_AFTER_SHARED_PASS'
  result=json.loads(durable(f'support_depth_v2/stage{oldstage}/support.json',head));assert result['status']=='COMPLETE' and result['identities_accounted']==1575
  b=gzip.decompress(durable(f'support_depth_v2/stage{oldstage}/validity.bin.gz',head));assert hashlib.sha256(b).hexdigest()==result['validity_sha256'];pieces.insert(0,np.frombuffer(b,np.uint8).reshape(1575,8064))
 # A completed or attempted stage is never automatically retried.
 try:api('/repos/'+REPO+'/contents/support_depth_v2/stage'+str(stage)+'/request_intent.json?ref='+head)
 except urllib.error.HTTPError as e:assert e.code==404
 else:raise RuntimeError('STAGE_ALREADY_ATTEMPTED_NO_AUTOMATIC_REPLAY')
 intent={'stage':stage,'block':block,'identities':1575,'protocol_sha256':sha(R/P),'cutoff_sha256':sha(R/C),'implementation_freeze_sha256':sha(R/'research_core_v4/state/STRICT_PREOUTCOME_V2_CURRENT_WAVE_OPERATIONAL_INFERENCE_V2_DEPTH_IMPLEMENTATION_FREEZE_V1.json'),'machine_preflight_sha256':hashlib.sha256(canonical(pre)).hexdigest(),'extension_implementation_freeze_sha256':sha(R/F),'extension_certificate_sha256':sha(R/'research_core_v4/state/STRICT_PREOUTCOME_OPERATIONAL_V2_EXTENDED_24_WEEK_CERTIFICATE_V1.json'),'broker_requests_so_far_this_stage':0,'run_id':int(os.environ['GITHUB_RUN_ID']),'no_raw_persistence':True}
 prefix=f'support_depth_v2/stage{stage}/';head=put(head,{prefix+'request_intent.json':canonical(intent)},'Freeze exactly one next nonoverlapping support-only28day request intent')
 from readonly import ReadOnlyTransport,send_page
 from research_core_v4 import shallow_m5_support_v2 as decoder,shallow_m5_support_v2_production as route,shallow_m5_support_v2_boundary_v4 as boundary,current_wave_support_worker_v1 as worker
 roster=json.loads((R/ROSTER).read_bytes())['entries'];assert len(roster)==1575
 dm=json.loads((R/S/'BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_SYMBOL_DIGITS_MAP.json').read_bytes());digits=decoder.digits_lookup(dm);assert all(e['SYMBOL_ID'] in digits for e in roster)
 bits=np.zeros((1575,8064),np.uint8);identity_records=[];tr=ReadOnlyTransport();tr.stage=stage;limiter=route.RateLimiter();old=(worker.START,worker.END,worker.G);worker.START=start;worker.END=end;worker.G=8064
 try:
  account=route.authenticate_segment(tr,os.environ['CTRADER_CLIENT_ID'],os.environ['CTRADER_CLIENT_SECRET'],os.environ['CTRADER_ACCESS_TOKEN'])
  for i,e in enumerate(roster):
   symbol=e['SYMBOL_ID'];ctx=decoder.RequestContext(f'V2S{stage}I{i}P1',account,symbol,start*1000,(end-300)*1000);seen=set();rawcount=0;validcount=0
   for pageidx in range(1,4):
    page=send_page(tr,ctx,digits[symbol],limiter);rawcount+=page.geometry.raw_response_count
    for row in page.canonical_rows:
     t=worker.timestamp(row['time_utc']);seg=(t-start)//(7*86400)+1;k,flags=worker.project(row,int(seg),digits[symbol]);assert 0<=k<8064 and k not in seen,'DUPLICATE_OR_OUTSIDE_BLOCK';seen.add(k);bits[i,k]=flags;validcount+=1;row.clear()
    decision=boundary.pagination_decision_v4(ctx=ctx,geometry=page.geometry,has_more_present=page.has_more_present,has_more_value=page.has_more_value,page_index=pageidx)
    page=None
    if decision.fail_closed:raise RuntimeError('PAGINATION_'+decision.reason)
    if decision.complete:break
    ctx=boundary.next_context_v4(ctx,decision,next_client_msg_id=f'V2S{stage}I{i}P{pageidx+1}')
   else:raise RuntimeError('PAGE_CAP_FAIL_CLOSED')
   identity_records.append({'roster_index':i,'symbol_id':symbol,'raw_rows':rawcount,'canonical_unique_rows':validcount,'missing_grid_rows':8064-validcount,'valid_OHLC_rows':int(((bits[i]&3)==3).sum()),'valid_required_fields_rows':int(((bits[i]&7)==7).sum()),'pages':pageidx,'complete':True})
   if (i+1)%64==0 or i==1574:
    shard=i//64;lo=shard*64;payload={prefix+f'validity_shards/{shard:03d}.bin.gz':gzip.compress(bits[lo:i+1].tobytes(),mtime=0),prefix+'request_ledger.json':canonical(tr.ledger),prefix+'identities.json':canonical(identity_records),prefix+'checkpoint.json':canonical({'stage':stage,'completed_identities':i+1,'total_identities':1575,'counters':counters(tr.ledger),'raw_persisted':False,'original_available_at':'UNKNOWN'})};head=put(head,payload,'Support-only Boolean checkpoint '+str(stage)+' identities '+str(i+1))
 except BaseException as exc:
  report={'schema':'mxm.operational-v2.support-depth-operational-blocker.v1','stage':stage,'status':'OPERATIONAL_BLOCKER','classification':getattr(exc,'classification',type(exc).__name__),'reason':str(exc)[:300],'identities_completed':len(identity_records),'counters':counters(tr.ledger),'no_retry':True,'no_power_result':True,'run_id':int(os.environ['GITHUB_RUN_ID']),'raw_persisted':False,'real_economic_values':0,'original_available_at':'UNKNOWN','protected_forward_opened':False,'confirmation_opened':False,'orders':0,'uncommitted_physical_IO_certainty':'If the worker were killed before this checkpoint, uncommitted attempts would be unknown; no automatic retry is authorized.'}
  head=put(head,{prefix+'blocker.json':canonical(report),prefix+'request_ledger.json':canonical(tr.ledger),prefix+'identities.json':canonical(identity_records)},'Fail closed at first real support-only route blocker');report['durable_head']=head;print('DEPTH_BLOCKER='+json.dumps(report,sort_keys=True),flush=True);return report
 finally:tr.close();worker.START,worker.END,worker.G=old
 assert len(identity_records)==1575 and len({x['symbol_id'] for x in identity_records})==1575
 support={'schema':'mxm.operational-v2.support-depth-block.v1','status':'COMPLETE','stage':stage,'block':block,'identities_accounted':1575,'identity_order_sha256':hashlib.sha256(canonical([x['SYMBOL_ID'] for x in roster])).hexdigest(),'validity_sha256':hashlib.sha256(bits.tobytes()).hexdigest(),'counters':counters(tr.ledger),'run_id':int(os.environ['GITHUB_RUN_ID']),'raw_persisted':False,'real_values':0,'original_available_at':'UNKNOWN_UNCHANGED','protected_forward_opened':False,'confirmation_opened':False,'orders':0}
 pieces.insert(0,bits);cumulative=np.concatenate(pieces,axis=1);out=R/'depth_geometry';daily,geometry=derive(cumulative,roster,start,out);gh=sha(out/'geometry.json')
 payload={prefix+'validity.bin.gz':gzip.compress(bits.tobytes(),mtime=0),prefix+'support.json':canonical(support),prefix+'request_ledger.json':canonical(tr.ledger),prefix+'identities.json':canonical(identity_records)}
 for path in out.iterdir():payload[prefix+'cumulative/'+path.name]=path.read_bytes()
 manifest={p:hashlib.sha256(b).hexdigest() for p,b in payload.items()};payload[prefix+'frozen_geometry_manifest.json']=canonical({'stage':stage,'protocol_sha256':sha(R/P),'files_sha256':manifest,'geometry_sha256':gh,'daily_mask_sha256':hashlib.sha256(daily.tobytes()).hexdigest(),'frozen_before_power':True});head=put(head,payload,'Freeze exact cumulative nonoutcome masks and geometry before synthetic power')
 result=run_power(daily,gh);result.update({'stage':stage,'calendar_depth_days':28*(stage+1),'mask_freeze_commit':head,'run_id':int(os.environ['GITHUB_RUN_ID'])});head=put(head,{prefix+'power.json':canonical(result)},'Immutable V2 synthetic full-procedure power on frozen exact masks');print('DEPTH_RESULT='+json.dumps({'support':support,'power':result,'durable_head':head},sort_keys=True),flush=True)
 # Stop immediately after coarse-stage power; no refinement in this task.
 return result

def refine(bits,roster,start,head,stage):
 trials=[];original_days=bits.shape[1]//288;source_min={};shared_min=None
 for removed in range(0,original_days-27,7):
  days=original_days-removed;out=R/'refine_geometry';daily,geometry=derive(bits[:,removed*288:],roster,start+removed*86400,out);gh=sha(out/'geometry.json');prefix=f'support_depth_v2/refinement/{days}days/'
  payload={prefix+p.name:p.read_bytes() for p in out.iterdir()};head=put(head,payload,'Freeze already acquired exact refinement geometry before power; broker requests zero')
  r=run_power(daily,gh);r.update({'calendar_depth_days':days,'mask_freeze_commit':head,'new_broker_requests':0});head=put(head,{prefix+'power.json':canonical(r)},'Fixed V2 refinement synthetic power on already observed masks');trials.append({'depth_days':days,'shared_ready':r['shared_ready'],'source_ready':r['source_ready']})
  for s,ok in r['source_ready'].items():
   if ok:source_min[s]=days
  if r['shared_ready']:shared_min=days
  else:break
 # Source-specific results are the shortest observed passing depths in the evaluated deterministic path, not an unobserved global minimum.
 plan={'schema':'mxm.operational-v2.refined-support-depth-plan.v1','resolution_days':7,'source_specific_observed_power_ready_depth_days':source_min,'shared_observed_power_ready_depth_days':shared_min,'refinement_trials':trials,'already_observed_from_utc':datetime.fromtimestamp(start,timezone.utc).isoformat(),'end_exclusive_utc':'2026-09-17T00:00:00Z','mask_only_history_discarded_numeric_rows':True,'later_economic_history':'Reacquire required observed interval only after independent audit and a separate economic-response authority. No raw rows were retained.','new_broker_requests_in_refinement':0,'economic_acquisition_executed':False,'stop':'INDEPENDENT_AUDIT'}
 head=put(head,{'support_depth_v2/refined_plan.json':canonical(plan)},'Freeze first passing observed depth refinement and plan-only economic requirement');print('REFINEMENT_RESULT='+json.dumps({'plan':plan,'durable_head':head},sort_keys=True),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--stage',type=int,required=True);a=p.parse_args();main(a.stage)
