"""Minimal event-time quote scope ONLY for corrected robust gross survivors.

Reconstructs signal indices without opening new response outcomes. No broker
requests, no credentials, no protected-forward bytes, no order placement.
"""
import argparse,csv,gzip,io,json,zipfile
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
import numpy as np
from research_core_v3.model import Bar,Series,_dt
from research_core_v3.fast_engine import Features
from research_core_v3.corrected_semantics import dependency_start,exact_segments
from tools.run_v3_broad_surface import canonical,sha,ORIGINAL_SHA

def main():
 p=argparse.ArgumentParser();p.add_argument('--original',required=True);p.add_argument('--delta',required=True);a=p.parse_args()
 root=Path(__file__).resolve().parents[1];state=root/'research_core_v3/state';assessment=json.loads((state/'CORRECTED_REGION_ASSESSMENT_V2.json').read_text());inputs=json.loads((state/'PRIMARY_145_INPUT_MANIFEST_V1.json').read_text());manifest=json.loads((state/'CORRECTED_145_DEVELOPMENT_MANIFEST_V2.json').read_text());spec=json.loads((state/'FROZEN_EXPERIMENT_SPEC_V1.json').read_text())
 regions=defaultdict(list)
 for r in assessment['regions']:regions[r['symbol_id']].append(r)
 shards=[];total=0;windows_total=0
 for item in inputs['primary_series']:
  sid=item['symbol_id']
  if sid not in regions:continue
  with zipfile.ZipFile(a.original if item['source_archive_sha256']==ORIGINAL_SHA else a.delta) as z:data=z.read(item['file'])
  assert sha(data)==item['series_sha256']
  bars=tuple(Bar(_dt(r['time_utc']),*(float(r[k]) for k in ('open','high','low','close','tick_volume'))) for r in csv.DictReader(io.StringIO(data.decode('utf-8-sig'))));f=Features(Series(item['symbol'],sid,item['series_sha256'],bars));seg=exact_segments(bars);events={}
  for r in regions[sid]:
   rearm=next(m['rearm_bars'] for m in spec['mechanisms'] if m['name']==r['mechanism'])
   for params in r['parameters']:
    sig=f.signals(r['mechanism'],params);ids=np.flatnonzero((sig!=0)&f.context(r['context']));last=-10**12
    for raw in ids:
     i=int(raw)
     if i+12>=len(bars) or seg[i]!=seg[i+12] or i-last<rearm:continue
     last=i;start=dependency_start(r['mechanism'],params,r['context'],i)
     if start<0 or seg[start]!=seg[i]:continue
     key=(i,int(sig[i]));events.setdefault(key,{'decision_index':i,'direction':int(sig[i]),'entry_time_utc':bars[i+1].ts.isoformat(),'exit_time_utc':(bars[i+6].ts+timedelta(minutes=5)).isoformat(),'region_sha256s':set()})['region_sha256s'].add(r['region_sha256'])
  intervals=[]
  for e in events.values():
   e['region_sha256s']=sorted(e['region_sha256s'])
   for key in ('entry_time_utc','exit_time_utc'):
    t=_dt(e[key]);start=t-timedelta(seconds=2);end=t+timedelta(seconds=30)
    assert end<_dt(manifest['binding']['protected_forward_start'])
    intervals.append((int(start.timestamp()*1000),int(end.timestamp()*1000)))
  merged=[]
  for start,end in sorted(intervals):
   if merged and start<=merged[-1][1]:merged[-1][1]=max(end,merged[-1][1])
   else:merged.append([start,end])
  doc={'symbol_id':sid,'symbol':item['symbol'],'source_series_sha256':item['series_sha256'],'events':[events[k] for k in sorted(events)],'bid_and_ask_request_windows_ms':merged}
  blob=gzip.compress(canonical(doc),mtime=0);name=f'CORRECTED_FRICTION_SCOPE_V2_{sid}.json.gz';(state/name).write_bytes(blob);shards.append({'path':name,'sha256':sha(blob),'symbol_id':sid,'events':len(events),'windows':len(merged)});total+=len(events);windows_total+=len(merged)
 plan={'schema':'mxm.research-core-v3.corrected-minimal-friction-evidence.v2','source_region_assessment_sha256':assessment['sha256'],'source_corrected_surface_sha256':manifest['sha256'],'implementation_sha256':sha(Path(__file__).read_bytes()),'status':'COST_UNRESOLVED','acquisition_performed':False,'gross_survivor_symbols':len(regions),'gross_survivor_regions':len(assessment['regions']),'unique_symbol_decision_direction_events':total,'merged_quote_windows':windows_total,'shards':shards,'quote_types':['BID','ASK'],'horizon_bars':6,'delay_sensitivity_seconds':[0,1,5,30],'quote_max_age_seconds':2,'slippage_sensitivity':'0,0.25,0.5,1 contemporaneous spread per fill; scenario bounds, not observed fills','historical_api':'Pepperstone cTrader Open API ProtoOAGetTickDataReq; pagination hasMore; request duration at most 604800000 ms','symbol_account_identity':'MUST_MATCH_ACCEPTED_PEPPERSTONE_ACCOUNT_FINGERPRINT_AND_SYMBOL_ID','protected_forward_opened':False,'missing_quote_policy':'COST_UNRESOLVED; NEVER_SUBSTITUTE_CURRENT_SPREAD','additional_required_authentic_evidence':['point-in-time commission and currency conversion','minimum volume and volume step; point-in-time applicability','symbol-specific margin and leverage tiers; point-in-time applicability','swap schedule where holding can incur rollover','session/holiday/trading-state restrictions','delay/slippage sensitivity; no guaranteed OHLC open fill'],'existing_evidence_audit':{'archives':'authenticated M5 OHLC only; no event-time bid/ask streams','legacy_quote_acceptance':'raw tick bytes declared retained locally, not transferred into repository','coarse_summaries':'not event-time historical evidence for this corrected surface; not applied'},'recovery_priority':'reuse matching authentic existing local tick chunks first; acquire only missing listed windows; no M5 recollection','freeze_gate':'CLOSED_UNTIL_AUTHENTIC_COSTS_AND_ALL_OTHER_GATES_PASS','confirmation_ready':False}
 plan['sha256']=sha(canonical(plan));(state/'CORRECTED_MINIMAL_FRICTION_EVIDENCE_PLAN_V2.json').write_text(json.dumps(plan,sort_keys=True,indent=2)+'\n');print(json.dumps({k:plan[k] for k in ('sha256','gross_survivor_symbols','gross_survivor_regions','unique_symbol_decision_direction_events','merged_quote_windows')}))
if __name__=='__main__':main()
