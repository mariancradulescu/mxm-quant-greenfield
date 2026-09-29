"""Outcome-blind full-frontier probe and resumable Pepperstone M5 acquisition."""
from __future__ import annotations
import csv
import hashlib
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from competition.frontier_data_capture import (
    FrontierDataCaptureRunner, _plain, _windows, _write_rows, _inspect_csv,
    _deterministic_zip, _sha_file, normalize_m5, canonicalize_m5_csv,
)
from m6.ctrader_capture import (
    CaptureContractError, MappingError, account_fingerprint, atomic_write_json,
    live_account_candidates, scan_bundle_for_secrets, select_live_pepperstone_account,
)
from m6.ctrader_proto.OpenApiMessages_pb2 import (
    ProtoOAApplicationAuthReq, ProtoOAAccountAuthReq,
    ProtoOAGetAccountListByAccessTokenReq, ProtoOATraderReq,
    ProtoOASymbolsListReq, ProtoOASymbolByIdReq, ProtoOAGetTrendbarsReq,
)
from m6.ctrader_proto.OpenApiModelMessages_pb2 import ProtoOATrendbarPeriod
from m6.ctrader_transport import LIVE_HOST, LIVE_PORT, StdlibCTraderTransport
from research_v3.capture_identity import build_capture_manifest

FRONTIER_REL = 'evidence/CROSS_SECTIONAL_PEER_COHORT_INDEX_V1.json'
FEASIBILITY_REL = 'data/PEPPERSTONE_CURRENT_EUR200_SYMBOL_FEASIBILITY_INDEX_EPOCH22_V1.json'
PROTECTED = '2026-09-17T12:02:58Z'
PROBE = {'start_utc':'2026-09-02T00:00:00Z','end_utc':'2026-09-16T23:59:59Z'}
DEVELOPMENT = {'start_utc':'2026-03-17T00:00:00Z','end_utc':'2026-09-16T23:59:59Z'}
SCHEMA = 'mxm.research-core-v3.full-frontier-quality-acquisition.v1'
OUTPUT = 'MXM_RESEARCH_CORE_V3_SELECTED_M5_DEVELOPMENT.zip'

def canonical_hash(o):
    return hashlib.sha256(json.dumps(o,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def frontier(root):
    peer=json.loads((Path(root)/FRONTIER_REL).read_text())
    feasibility=json.loads((Path(root)/FEASIBILITY_REL).read_text())
    identities=peer['identities']
    if len(identities)!=1576 or len({int(x['symbol_id']) for x in identities})!=1576:
        raise CaptureContractError('full exact identity frontier is not 1576 unique IDs')
    if int(feasibility['current_counts']['current_eligible_post_exclusion_frontier'])!=1576:
        raise CaptureContractError('broker feasibility authority changed')
    return identities,feasibility

def validate_rows(rows, expected_start, expected_end):
    from datetime import datetime
    prev=None
    for row in rows:
        ts=datetime.fromisoformat(row['time_utc'].replace('Z','+00:00'))
        if prev is not None and ts<=prev: raise CaptureContractError('M5 timestamps not increasing')
        if ts.minute%5 or ts.second or ts.microsecond: raise CaptureContractError('off-grid M5 timestamp')
        o,h,l,c=map(float,(row['open'],row['high'],row['low'],row['close']))
        if not (l<=o<=h and l<=c<=h and l>0): raise CaptureContractError('OHLC invariant')
        if not expected_start<=row['time_utc']<=expected_end: raise CaptureContractError('out of window')
        prev=ts

def select_core(table):
    # Metadata quality gate, then a verified bounded broker-history gate. No response variables.
    selected=[]
    for row in table:
        if row['identity_status']!='VERIFIED' or row['schedule_minutes_per_week']<6000:
            row['selection_or_deferral_reason']='IDENTITY_UNVERIFIED_OR_LIMITED_SESSION'
        elif row['probe_rows']==0:
            row['selection_or_deferral_reason']='AUTHENTIC_ZERO_HISTORY_IN_PROBE'
        elif row['probe_rows']<0.8*row['schedule_minutes_per_week']*2/5:
            row['selection_or_deferral_reason']='INSUFFICIENT_VERIFIED_M5_COVERAGE_VERSUS_BROKER_SCHEDULE'
        elif row['probe_gap_fraction']>0.10:
            row['selection_or_deferral_reason']='POOR_CONTINUITY_IN_BOUNDED_PROBE'
        else:
            row['initial_core_selected']=True
            row['selection_or_deferral_reason']='HIGH_COVERAGE_VERIFIED_M5_HISTORY_AND_EUR200_FEASIBILITY'
            selected.append(row)
    return selected

class AdaptiveCollector(FrontierDataCaptureRunner):
    def __init__(self, *, client_id,client_secret,access_token,config,repo_root,progress=print,transport=None):
        self.root=Path(repo_root); self.identities,self.feasibility=frontier(self.root)
        self.plan={'schema':SCHEMA,'source_environment':self.feasibility['source_environment'],
            'account_fingerprint_sha256':self.feasibility['account_fingerprint_sha256'],
            'frontier_sha256':_sha_file(self.root/FRONTIER_REL), 'probe':PROBE,
            'interval':DEVELOPMENT,'protected_forward_start':PROTECTED,
            'resolution':'M5','outcomes_opened':False,'window_days':7}
        self.plan_sha=canonical_hash(self.plan)
        self.client_id=client_id;self.client_secret=client_secret;self.access_token=access_token
        self.config=dict(config);self.progress=progress
        self.transport=transport or StdlibCTraderTransport(LIVE_HOST,LIVE_PORT,response_timeout=60)
        self.work=self.root/'.research_core_v3_capture_work'/self.plan_sha[:16]
        self.bundle=self.work/'bundle';self.zip_path=self.root/OUTPUT
        self.state_path=self.work/'progress.json';self._app=False;self._account=None;self._last_hist=None
        self.lock=threading.RLock();self.stop=threading.Event();self.started=time.monotonic()
        self.state={}
    def _save(self):
        with self.lock:
            self.state['last_heartbeat_utc']=datetime.now(timezone.utc).isoformat()
            self.state['percentage_complete']=round(100*len(self.state['completed_units'])/self.state['total_work_units'],4)
            atomic_write_json(self.state_path,self.state)
    def _heartbeat(self):
        while not self.stop.wait(10):
            self._save()
            with self.lock:
                s=self.state
                self.progress('[HEARTBEAT] '+json.dumps({k:s.get(k) for k in ('last_heartbeat_utc','phase','current_symbol','current_symbol_id','current_work_unit','total_work_units','completed_work_units','completed_symbols','total_selected_symbols','current_symbol_rows','rows_total','requests_total','retry_count','zero_history_symbols','failed_symbols','last_successful_data_timestamp','percentage_complete')},sort_keys=True)+f' elapsed_s={int(time.monotonic()-self.started)} checkpoint={self.state_path}',flush=True) if self.progress is print else self.progress('[HEARTBEAT] '+json.dumps({k:s.get(k) for k in ('last_heartbeat_utc','phase','current_symbol','current_symbol_id','current_work_unit','total_work_units','completed_work_units','completed_symbols','total_selected_symbols','current_symbol_rows','rows_total','requests_total','retry_count','zero_history_symbols','failed_symbols','last_successful_data_timestamp','percentage_complete')},sort_keys=True))
    def _send(self,r,historical=False,retries=3):
        try:
            result=super()._send(r,historical=historical,retries=retries)
            if historical:
                with self.lock:self.state['requests_total']+=1
            return result
        except Exception:
            with self.lock:self.state['retry_count']+=max(0,retries-1)
            raise
    def _auth(self):
        self._send(ProtoOAApplicationAuthReq(clientId=self.client_id,clientSecret=self.client_secret));self._app=True
        accounts=[_plain(x) for x in self._send(ProtoOAGetAccountListByAccessTokenReq(accessToken=self.access_token)).ctidTraderAccount]
        saved=self.config.get('ctid_trader_account_id')
        try: account=select_live_pepperstone_account(accounts,account_override=saved)
        except MappingError:
            selector=self.config.get('account_selector')
            if saved is not None or not callable(selector): raise
            account=select_live_pepperstone_account(accounts,account_override=int(selector(live_account_candidates(accounts))))
        aid=int(account['ctidTraderAccountId']);self._account=aid
        if account_fingerprint(aid)!=self.plan['account_fingerprint_sha256']:raise MappingError('account fingerprint mismatch')
        self._send(ProtoOAAccountAuthReq(ctidTraderAccountId=aid,accessToken=self.access_token))
        trader=_plain(self._send(ProtoOATraderReq(ctidTraderAccountId=aid)).trader)
        if 'pepperstone' not in str(trader.get('brokerName','')).lower() and 'pepperstone' not in str(account.get('brokerTitleShort','')).lower():raise MappingError('broker mismatch')
        light={int(x.symbolId):_plain(x) for x in self._send(ProtoOASymbolsListReq(ctidTraderAccountId=aid,includeArchivedSymbols=False)).symbol}
        full={}
        ids=[int(x['symbol_id']) for x in self.identities]
        for offset in range(0,len(ids),64):
            req=ProtoOASymbolByIdReq(ctidTraderAccountId=aid);req.symbolId.extend(ids[offset:offset+64])
            for item in self._send(req).symbol:full[int(item.symbolId)]=_plain(item)
        return aid,light,full
    def _fetch_window(self,aid,sid,digits,start,end):
        rows={}; pages=0; page_to=end
        while page_to>=start:
            q=ProtoOAGetTrendbarsReq(ctidTraderAccountId=aid,symbolId=sid,period=ProtoOATrendbarPeriod.Value('M5'),fromTimestamp=start,toTimestamp=page_to,count=5000)
            r=self._send(q,historical=True);bars=[_plain(x) for x in r.trendbar];pages+=1
            for row in normalize_m5(bars,digits=digits,start_utc=self.plan['interval']['start_utc'] if start!=_windows(PROBE['start_utc'],PROBE['end_utc'],14)[0][0] else PROBE['start_utc'],end_utc=PROBE['end_utc'] if start==_windows(PROBE['start_utc'],PROBE['end_utc'],14)[0][0] else DEVELOPMENT['end_utc'],protected_utc=PROTECTED):
                old=rows.get(row['time_utc'])
                if old is not None and old!=row:raise CaptureContractError('conflicting duplicate')
                rows[row['time_utc']]=row
            if not getattr(r,'hasMore',False):break
            if not bars:raise CaptureContractError('hasMore without bars')
            nxt=min(int(x['utcTimestampInMinutes'])*60000 for x in bars)-1
            if nxt>=page_to or nxt<start:raise CaptureContractError('invalid pagination')
            page_to=nxt
        result=[rows[k] for k in sorted(rows)]
        validate_rows(result,DEVELOPMENT['start_utc'] if start!=_windows(PROBE['start_utc'],PROBE['end_utc'],14)[0][0] else PROBE['start_utc'],PROBE['end_utc'] if start==_windows(PROBE['start_utc'],PROBE['end_utc'],14)[0][0] else DEVELOPMENT['end_utc'])
        if result:self.state['last_successful_data_timestamp']=result[-1]['time_utc']
        return result,pages
    def _unit(self,key,aid,sid,digits,start,end):
        file=self.work/'units'/f'{key}.csv'; meta=file.with_suffix('.json');file.parent.mkdir(parents=True,exist_ok=True)
        if key in self.state['completed_units']:
            if not file.is_file() or not meta.is_file() or _sha_file(file)!=json.loads(meta.read_text())['sha256']:
                raise CaptureContractError('checkpointed work unit integrity mismatch')
            with file.open(newline='') as f:return list(csv.DictReader(f))
        rows,pages=self._fetch_window(aid,sid,digits,start,end)
        tmp=file.with_suffix('.tmp');_write_rows(tmp,rows,'w');tmp.replace(file)
        atomic_write_json(meta,{'sha256':_sha_file(file),'rows':len(rows),'pages':pages})
        with self.lock:
            self.state['completed_units'].append(key);self.state['completed_work_units']=len(self.state['completed_units'])
            self.state['rows_total']+=len(rows);self.state['current_symbol_rows']+=len(rows)
            self._save()
        return rows
    def run(self):
        self.work.mkdir(parents=True,exist_ok=True)
        if self.state_path.exists():
            self.state=json.loads(self.state_path.read_text())
            if self.state['plan_sha256']!=self.plan_sha:raise CaptureContractError('checkpoint plan mismatch')
        else:
            self.state={'plan_sha256':self.plan_sha,'selected_identity_manifest_sha256':None,'started_utc':datetime.now(timezone.utc).isoformat(),'phase':'FRONTIER_PROBE','current_symbol':None,'current_symbol_id':None,'current_work_unit':None,'total_work_units':1576+1576*len(_windows(DEVELOPMENT['start_utc'],DEVELOPMENT['end_utc'],7)),'completed_work_units':0,'completed_units':[],'completed_symbols':0,'total_selected_symbols':0,'current_symbol_rows':0,'rows_total':0,'requests_total':0,'retry_count':0,'zero_history_symbols':0,'failed_symbols':0,'last_successful_data_timestamp':None,'resumable_checkpoint':str(self.state_path)}
            self._save()
        t=threading.Thread(target=self._heartbeat,daemon=True);t.start()
        try:
            self.transport.connect();self._workflow()
        finally:
            self.stop.set();t.join(timeout=2);self.transport.close()
        return self.zip_path
    def _workflow(self):
        aid,light,full=self._auth()
        table=[];probe_windows=_windows(PROBE['start_utc'],PROBE['end_utc'],14)
        for x in self.identities:
            sid=int(x['symbol_id']);name=x['broker_symbol'];li=light.get(sid);fu=full.get(sid)
            valid=li is not None and fu is not None and li.get('symbolName')==name and li.get('enabled') is not False and int(fu.get('tradingMode',-1))==0
            row={'symbol':name,'symbol_id':sid,'asset_class':x['peer_coherence_metadata'].get('asset_class'),'product_type':x['peer_coherence_metadata'].get('product_type'),'current_accessibility':x['current_entry_accessible'],'directional_feasibility':x['directional_feasibility'],'shortability':x['directional_feasibility']=='BOTH_FEASIBLE','minimum_executable_volume':x['minimum_executable_volume'],'minimum_margin_estimate_for_EUR200':x['minimum_directional_margin_eur'],'schedule_minutes_per_week':x['schedule_minutes_per_week'],'schedule_continuity_class':x['peer_coherence_metadata'].get('coverage_bucket'),'identity_status':'VERIFIED' if valid else 'DRIFT','available_M5_history_start':None,'available_M5_history_end':None,'available_M5_row_count_or_verified_estimate':None,'probe_rows':0,'probe_gap_fraction':None,'gap_statistics':None,'timestamp_integrity':None,'OHLC_integrity':None,'outcome_blind_event_availability_when_preflighted':None,'effective_sample_potential':None,'data_quality_status':'UNKNOWN','initial_core_selected':False,'selection_or_deferral_reason':None}
            table.append(row)
            if not valid:raise MappingError(f'full frontier identity drift: {name}/{sid}')
            key=f'probe_{sid}'
            self.state.update(phase='FRONTIER_PROBE',current_symbol=name,current_symbol_id=sid,current_work_unit=key,current_symbol_rows=0);self._save()
            rows=self._unit(key,aid,sid,int(fu.get('digits',5)),*probe_windows[0])
            row['probe_rows']=len(rows);row['available_M5_row_count_or_verified_estimate']=len(rows)
            if rows:
                row['available_M5_history_start']=rows[0]['time_utc'];row['available_M5_history_end']=rows[-1]['time_utc']
                gaps=sum((datetime.fromisoformat(b['time_utc'].replace('Z','+00:00'))-datetime.fromisoformat(a['time_utc'].replace('Z','+00:00'))).total_seconds()>300 for a,b in zip(rows,rows[1:]))
                row['gap_statistics']={'probe_gap_count':gaps};row['probe_gap_fraction']=gaps/max(1,len(rows)-1)
                row['data_quality_status']='PROBED_NONEMPTY';row['timestamp_integrity']='PASS';row['OHLC_integrity']='PASS'
                row['effective_sample_potential']=len(rows)
            else:
                self.state['zero_history_symbols']+=1;row['probe_gap_fraction']=1.0;row['data_quality_status']='AUTHENTIC_ZERO_HISTORY_IN_PROBE'
        selected=select_core(table)
        if not selected:raise CaptureContractError('no identities passed bounded history quality gate')
        manifest={'schema':SCHEMA,'plan_sha256':self.plan_sha,'symbols':[{'broker_symbol':r['symbol'],'symbol_id':r['symbol_id']} for r in selected],'selection_law':'verified both-direction EUR200, schedule >=6000 min/week, at least 80% of two-week scheduled M5 bars in bounded probe, gap fraction <=0.10; no outcomes','interval':DEVELOPMENT,'protected_forward_start':PROTECTED}
        manifest['sha256']=canonical_hash(manifest)
        prior_selected=self.state.get('selected_identity_manifest_sha256')
        self.state['total_selected_symbols']=len(selected)
        windows=_windows(DEVELOPMENT['start_utc'],DEVELOPMENT['end_utc'],7)
        if prior_selected not in (None,manifest['sha256']):
            raise CaptureContractError('frozen selected identity manifest changed on resume')
        self.state['selected_identity_manifest_sha256']=manifest['sha256']
        self.state['total_work_units']=1576+len(selected)*len(windows);self._save()
        self.bundle.mkdir(exist_ok=True);atomic_write_json(self.bundle/'DATA_QUALITY_TABLE.json',{'frontier_count':len(table),'rows':table});atomic_write_json(self.bundle/'SELECTED_IDENTITY_MANIFEST.json',manifest)
        results=[]
        for idx,r in enumerate(selected,1):
            sid=r['symbol_id'];name=r['symbol'];allrows={};self.state.update(phase='DEEP_DEVELOPMENT_CAPTURE',current_symbol=name,current_symbol_id=sid,current_symbol_rows=0)
            for wi,(start,end) in enumerate(windows):
                key=f'deep_{sid}_{wi:03d}';self.state['current_work_unit']=key;self._save()
                for bar in self._unit(key,aid,sid,int(full[sid].get('digits',5)),start,end):
                    old=allrows.get(bar['time_utc'])
                    if old is not None and old!=bar:raise CaptureContractError('conflicting cross-window duplicate')
                    allrows[bar['time_utc']]=bar
            path=self.bundle/'raw'/f'{sid}_M5.csv';path.parent.mkdir(exist_ok=True)
            rows=[allrows[k] for k in sorted(allrows)];validate_rows(rows,DEVELOPMENT['start_utc'],DEVELOPMENT['end_utc'])
            _write_rows(path,rows,'w');meta=_inspect_csv(path)
            results.append({'broker_symbol':name,'symbol_id':sid,'file':path.relative_to(self.bundle).as_posix(),**meta})
            self.state['completed_symbols']=idx;self._save();self.progress(f'[SERIES {idx}/{len(selected)}] {name}: {len(rows)} authentic M5 rows')
        payload={'schema':SCHEMA,'status':'CAPTURE_COMPLETE','plan_sha256':self.plan_sha,'selected_identity_manifest_sha256':manifest['sha256'],'account_fingerprint_sha256':self.plan['account_fingerprint_sha256'],'source_environment':self.plan['source_environment'],'resolution':'M5','classification':'DEVELOPMENT_ONLY','requested_interval':DEVELOPMENT,'series':results,'total_m5_rows':sum(r['row_count'] for r in results),'protected_forward_opened':False,'economic_outcomes_opened':0,'orders_placed':False,'account_mutation':False}
        payload_path=self.bundle/'V3_CAPTURE_PAYLOAD.json';atomic_write_json(payload_path,payload)
        provenance=build_capture_manifest(capture_session_id='research-core-v3-selected-'+manifest['sha256'][:16],capture_schema=SCHEMA,tool_version='FULL_FRONTIER_GENERIC_V2',account_fingerprint=self.plan['account_fingerprint_sha256'],source_environment=self.plan['source_environment'],capture_start_utc=DEVELOPMENT['start_utc'],capture_end_utc=DEVELOPMENT['end_utc'],completion_state='COMPLETE',canonical_payloads={'V3_CAPTURE_PAYLOAD.json':payload_path.read_bytes()},original_collector_package_sha256=self.config.get('collector_package_sha256'),read_only_assertion=True,economic_outcomes_opened=0,orders_placed=False,account_mutation=False,protected_evidence_opened=False)
        atomic_write_json(self.bundle/'CAPTURE_MANIFEST.json',provenance)
        (self.bundle/'CHECKSUMS.sha256').write_text(''.join(f'{_sha_file(p)}  {p.relative_to(self.bundle).as_posix()}\n' for p in sorted(self.bundle.rglob('*')) if p.is_file() and p.name!='CHECKSUMS.sha256'))
        scan_bundle_for_secrets(self.bundle,[self.client_secret,self.access_token])
        digest=_deterministic_zip(self.bundle,self.zip_path)
        self.state['phase']='CAPTURE_COMPLETE';self._save()
        self.progress(f'CAPTURE_COMPLETE final_zip_path={self.zip_path} final_zip_sha256={digest} selected_identity_count={len(selected)} successful_nonempty_identity_count={sum(r["row_count"]>0 for r in results)} authentic_zero_history_identity_count={sum(r["row_count"]==0 for r in results)} failed_identity_count=0 total_M5_rows={payload["total_m5_rows"]} history_start_utc={DEVELOPMENT["start_utc"]} history_end_utc={DEVELOPMENT["end_utc"]} elapsed_seconds={int(time.monotonic()-self.started)} integrity_status=PASS')
