"""Compile existing cost availability only; never reads AIDR events or computes costs."""
import pathlib,json,csv,io,zipfile,gzip,hashlib,math
from datetime import datetime,timezone
START=1787184000000
END=1789603200000
HASHES={
'MXM_M6_TIER1_COST_EVIDENCE_V3.zip':'f187010d55a6f444827592e23158187c3985c5c3af4631f4e31c53c8a84a1360',
'MXM_M6_TIER1_PREOPEN_0930_SUPPLEMENT_V1.zip':'8171ce2d68fef0ac0241b88e914725c16a301e36ae836f766efff4da8aabe798',
'MXM_BREAKOUT_FADE_NETH25_TRANSACTION_LOCAL_COST_V1.zip':'801b863d396a117d787b73dd673003cf79a4c9ffa178a38d0c928aba241243f0',
'MXM_V3_GLOBAL_FRICTION_TRIAGE_EVIDENCE_V1.zip':'44c3d7a9ab68d712714175b6d6e776e4d8a8a2fa6f47c54869d133e7cb8dd13a',
'MXM_V3_WAVE2_GLOBAL_FRICTION_TRIAGE_EVIDENCE_V1.zip':'8773ebe0224a92d5236146b40bedef83617e7927e60a076fccddabb8dca4c0fe',
'MXM_V3_WINNER_FIRST_FRICTION_SCREEN_EVIDENCE_V1.zip':'3f9948a04d3fa96690c39c66f4e9d6c277e102c34e4014ca36f8634de24bffd7',
'MXM_PW02_CTRADER_CAPTURE_da9e9a65f5c8_RECONCILED.zip':'88c68f1724eba71ef58fe02a929c935dc1cbf4be432897db599be7b37fd4ae72',
'BROKER_NATIVE_COMPETITION_OPPORTUNITY_MAP_V2.csv':'c2b16c3fc0419ec335ebbd67e0af09043e60a476516db01c55550d661b5f4130'}
def canonical(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def ms(x):return int(datetime.fromisoformat(x.replace('Z','+00:00')).timestamp()*1000)
def two(b,a):
 try:return math.isfinite(float(b)) and math.isfinite(float(a)) and 0<float(b)<=float(a)
 except (TypeError,ValueError):return False
def compile_sources(root):
 sources=[];aux=[]
 for filename,digest in HASHES.items():
  raw=(pathlib.Path(root)/filename).read_bytes();assert sha(raw)==digest
  if filename.endswith('.csv'):
   rows=list(csv.DictReader(io.StringIO(raw.decode())))
   aux.append({'source':filename,'sha256':digest,'interpretation':'CURRENT_CONTRACT_SNAPSHOT_NOT_HISTORICAL_TERMS','symbol_ids':sorted(int(r['symbol_id']) for r in rows)})
   continue
  z=zipfile.ZipFile(io.BytesIO(raw));assert z.testzip() is None
  check=next(n for n in z.namelist() if n=='CHECKSUMS.sha256' or n.endswith('/CHECKSUMS.sha256'));base=check[:-len('CHECKSUMS.sha256')]
  for line in z.read(check).decode().splitlines():
   if not line.strip():continue
   h,n=line.split(maxsplit=1);n=n.strip().lstrip('*');n=base+n if base+n in z.namelist() else n
   assert sha(z.read(n))==h
  if 'PW02' in filename:
   members={}
   for n in z.namelist():
    if '/conversion_raw/' in n and n.endswith('.csv'):members[n]=sha(z.read(n))
   assert sorted(members.values())==sorted(['bce32af6ef251115d0628d746af16849a7ac23d7185a716670b0b22a4f09adde','2f25be36c7599937e120f9bd1f5cf44a62b3edf383e8735214f3bd58370009cf'])
   aux.append({'source':filename,'sha256':digest,'conversion_members':members,'interpretation':'COMPLETED_M15_PRICE_SERIES_NOT_EXECUTABLE_CONVERSION_OR_FEE_RECEIPTS'})
   continue
  members={}
  for n in z.namelist():
   if n.endswith('/') or n.startswith('MXM_') and not ('TIER1' in filename):continue
   # All relevant complete member bytes are hashed; only frozen date-domain availability is transported.
   if 'M15_BOUNDARY_QUOTE_EVIDENCE.csv' in n:
    symbol=127 if '/US500_' in n else 126
    rows=list(csv.DictReader(io.StringIO(z.read(n).decode())))
    records=[{'timestamp_ms':int(r['boundary_timestamp_ms']),'two_sided':two(r['causal_bid'],r['causal_ask']),'fresh':None,
      'bid_age_ms':r['causal_bid_age_ms'],'ask_age_ms':r['causal_ask_age_ms'],'row_sha256':sha(canonical(r))}
      for r in rows if START<=int(r['boundary_timestamp_ms'])<=END]
    sources.append({'source':filename,'zip_sha256':digest,'member':n,'member_sha256':sha(z.read(n)),'symbol_id':symbol,'kind':'BOUNDARY','semantics':'CAUSAL_QUOTES_NO_FROZEN_FRESHNESS_NO_FILL','records':records})
   elif n=='event_boundary_costs.csv':
    rows=list(csv.DictReader(io.StringIO(z.read(n).decode())))
    records=[{'entry_ms':ms(r['entry_boundary_utc']),'exit_ms':ms(r['exit_boundary_utc']),'source_event_direction':r['event_direction'],
     'resolved':r['cost_state']=='TRANSACTION_LOCAL_COST_RESOLVED','row_sha256':sha(canonical(r))} for r in rows if START<=ms(r['entry_boundary_utc'])<=END]
    assert all(r['event_direction'] in ('UP','DOWN') for r in rows)
    sources.append({'source':filename,'zip_sha256':digest,'member':n,'member_sha256':sha(z.read(n)),'symbol_id':269,'kind':'JOINT','semantics':'OTHER_LAW_JOINT_COST_ROW_NOT_EXECUTED_FILL','records':records})
   elif n.startswith('derived/') and n.endswith('.jsonl.gz'):
    hours=[json.loads(line) for line in gzip.decompress(z.read(n)).splitlines()]
    assert len({h['symbol_id'] for h in hours})==1
    records=[]
    for h in hours:
     for r in h['rows']:
      t=r['boundary_ms'];q=r['d0s']
      if START<=t<=END:
       records.append({'timestamp_ms':t,'two_sided':two(q['bid'],q['ask']),'fresh':q['fresh'],
        'bid_age_ms':q['bid_age_ms'],'ask_age_ms':q['ask_age_ms'],'row_sha256':sha(canonical(r))})
    sources.append({'source':filename,'zip_sha256':digest,'member':n,'member_sha256':sha(z.read(n)),'symbol_id':hours[0]['symbol_id'],'kind':'BOUNDARY','semantics':'SAMPLED_D0_ONLY_NO_FILL_OR_TERMS','records':records})
   elif 'TIER1_PREOPEN' in filename and n.endswith('.csv'):
    # 09:30 ET is half-hour UTC: no fixed AIDR hourly clock. Generic bound is not a quote/fill.
    aux.append({'source':filename,'sha256':digest,'member':n,'member_sha256':sha(z.read(n)),'interpretation':'PREOPEN_HALF_HOUR_OR_OTHER_CANDIDATE_GENERIC_BOUND_NOT_TRANSFERRED'})
 return {'schema':'mxm.aidr.existing.cost.availability.v1','start_ms':START,'end_ms':END,'sources':sources,'auxiliary':aux,'source_sha256':HASHES,'compiled_without_event_access':True,'prices_costs_returns_transported':False}
if __name__=='__main__':
 import sys
 pathlib.Path(sys.argv[2]).write_bytes(canonical(compile_sources(sys.argv[1])))

