"""One new frozen input->native-CSharp causal M5 signed volume-flow DEVELOPMENT study.

The same 12-closed-bar rule is implemented in MxmVolumeFlowKernel.cs, wired to
the existing single native cBot's explicitly order-free observation. This R3
script reads ONLY already accepted original Pepperstone data; no broker contact,
new data, historical fill fiction, stage-C confirmation, or LIVE/DEMO orders.
The 10/20bps figures are hypothetical stress, not certified broker NET in EUR.
"""
from __future__ import annotations
import collections
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
from research_core_v4.laboratory import m5_authentic_envelope as env
from research_core_v4.laboratory import m5_causal_gross_development as old_source

ID="MXM-BE-M5-SIGNED-VOLUME-FLOW-20261101-V1"
ROWS=3355389
NAMES=1576
N_SHARDS=100
M5=300
FIRST=int(dt.datetime(2026,8,20,tzinfo=dt.timezone.utc).timestamp())
PROTECTED=int(dt.datetime(2026,9,17,tzinfo=dt.timezone.utc).timestamp())
OUT=env.ROOT/"verification/be-integrated-volume-flow-20261101"
HOLD=12
MAXV=1000000000
def need(cond,name):
 if not cond:raise RuntimeError("MXM_BE_FLOW_"+name)
def digest(raw):return hashlib.sha256(raw).hexdigest()
def flow_signal(history):
 """12 strictly completed M5 OHLCV bars; mirrors CSharp fixed coefficients."""
 if len(history)!=12:return 0
 older,recent=history[:6],history[6:]
 def pressure(q):
  v=sum(x[5] for x in q)
  return sum(10000*(x[4]/x[1]-1)*x[5] for x in q)/v if v else 0.
 a,b=pressure(older),pressure(recent)
 trend=10000*(recent[-1][4]/recent[0][1]-1)
 if b>=8 and b-a>=6 and abs(b)>=1.5*abs(a) and trend>=3:return 1
 if b<=-8 and a-b>=6 and abs(b)>=1.5*abs(a) and trend<=-3:return -1
 return 0

def parse(rows):
 result=[];last=0
 for row in rows:
  need(set(row)=={"time_utc","open","high","low","close","tick_volume"},"ROW_FIELDS")
  ts=int(dt.datetime.fromisoformat(row["time_utc"].replace("Z","+00:00")).timestamp())
  need(row["time_utc"].endswith("Z") and FIRST<=ts<PROTECTED and ts%M5==0 and ts>last,"SOURCE_CLOCK")
  op,hi,lo,cl=[float(row[x]) for x in ("open","high","low","close")]
  vol=float(row["tick_volume"])
  need(all(math.isfinite(x) for x in (op,hi,lo,cl,vol)) and
       0<lo<=min(op,cl)<=max(op,cl)<=hi and vol>=0,"SOURCE_OHLCV")
  # True source incompleteness/invalid volume cannot become zero-volume evidence.
  vol=int(vol) if vol<=MAXV and vol.is_integer() else -1
  result.append((ts,op,hi,lo,cl,vol))
  last=ts
 return result

def candidates(rows):
 """No feature reads future outcomes. Data discontinuity resets feature history."""
 history=collections.deque(maxlen=12)
 pending=[];last=None;nonoverlap_until=-1
 rejected_volume=0
 for i,x in enumerate(rows):
  t=x[0]
  if last is not None and t-last!=M5:history.clear()
  last=t
  if x[5]<0:
   history.clear();rejected_volume+=1;continue
  history.append(x)
  # Last closed candle's full OHLCV only exists at t+M5, never at its OPEN.
  decision=t+M5
  if len(history)!=12 or decision>=PROTECTED or t<=nonoverlap_until:continue
  side=flow_signal(list(history))
  if not side:continue
  entry=decision
  expiry=entry+HOLD*M5
  pending.append((i,side,entry,expiry))
  nonoverlap_until=t+HOLD*M5
 return pending,rejected_volume

def result_for(rows,offers):
 """Later open-to-open directional response: proxy, NOT executable BIDASK."""
 out=[]
 for i,side,entry,expiry in offers:
  ei=i+1;xi=ei+HOLD
  if xi>=len(rows):
   out.append((entry,side,None));continue
  a,b=rows[ei],rows[xi]
  if (a[0]!=entry or b[0]!=expiry or
      any(rows[j][0]-rows[j-1][0]!=M5 for j in range(i+1,xi+1))):
   out.append((entry,side,None));continue
  gross=10000*side*(b[1]/a[1]-1)
  need(math.isfinite(gross),"RESPONSE_NAN")
  out.append((entry,side,gross))
 return out

def selftest():
 start=int(dt.datetime(2026,8,25,10,tzinfo=dt.timezone.utc).timestamp())
 def mk(side):
  xs=[]
  for i in range(29):
   op=100+side*i*.03
   cl=op+side*(.01 if i<6 else .25 if i<12 else .01)
   xs.append((start+i*300,op,max(op,cl)+.01,min(op,cl)-.01,cl,10 if i<6 else 30))
  return xs
 for sign in (-1,1):
  src=mk(sign);need(flow_signal(src[:12])==sign,"CPP_FIXED_VECTOR")
  offers,invalid=candidates(src)
  need(len(offers)>=1 and invalid==0 and offers[0][1]==sign and offers[0][2]==src[11][0]+M5,"CAUSAL_SIGNAL")
  out=result_for(src,offers)
  need(out[0][2] is not None,"CAUSAL_EXIT_AFTER_DECISION")
  src[5]=(src[5][0]+600,)+src[5][1:]
  # Controlled synthetic gap cannot retain the previous 12-bar state.
  need(flow_signal(src[:11])==0,"WARMUP")
 need(flow_signal(mk(1)[:11])==0,"NO_PREMATURE_FEATURE")
 need(flow_signal(mk(1)[:6]+mk(-1)[6:12])==0,"OPPOSING_FLOW_HOLD")
 print("MXM_BE_VOLUME_FLOW_PYTHON_SOURCE_BLIND_SUCCESS")

def authentic():
 selftest()
 need(os.getenv("GITHUB_REPOSITORY")==env.REPO and
      os.getenv("GITHUB_EVENT_NAME")=="push" and
      os.getenv("GITHUB_REF")=="refs/heads/mxm-remediation-p0-p4-20261015-v1" and
      os.getenv("GITHUB_RUN_ATTEMPT")=="1","OFFICIAL_CUSTODY_FIRST_RUN")
 entries,manifesthash=old_source.load_market_geometry()
 from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
 from research_core_v4.shallow_m5_support_v2_production import decrypt_synthetic_package,encrypt_shard,public_spki_sha256
 result={"schema":"mxm.be.volume-flow.original-development-v1","id":ID,
  "original_release":env.RELEASE_IDENTITY,"manifest_sha256":manifesthash,
  "original_shards":0,"original_rows":0,"identities":0,"input_only_candidates":0,
  "complete_proxy_exits":0,"right_censored":0,"invalid_tick_volume_bars":0,
  "gross_bps_sum":0.,"scenario_after_10bps_sum":0.,"scenario_after_20bps_sum":0.,
  "weekly_proxies":{},"classification":"DEVELOPMENT_ONLY_NOT_BROKER_EUR_NET",
  "quote_side":"M5_NEXT_OPEN_PROXY_NOT_NATIVE_BIDASK",
  "cost_basis":"HYPOTHETICAL_10_20BPS_NOT_PEPERSTONE_CERTIFIED",
  "funding":"NOT_EVALUATED_NO_FICTITIOUS_EUR200_CAPITAL_PATH",
  "independent_confirmation":False,"historical_margin":False,
  "protected_forward_opened":False,"live_orders":0,"demo_orders":0,"cloud_activations":0,
  "broker_fills":0,"hard21_broker":False}
 # Per-opportunity prices/side/gross never published in public aggregate.
 private=[]
 with tempfile.TemporaryDirectory(prefix="mxm-be-volume-flow-") as tmp:
  root=Path(tmp);key,fp=_private_key_from_secret(root)
  need(fp=="464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11","EXISTING_RECIPIENT")
  market=root/"original";market.mkdir(mode=0o700)
  subprocess.run(["gh","release","download",env.RELEASE_IDENTITY,"--repo",env.REPO,
                  "--dir",str(market)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=900)
  need(len(list(market.iterdir()))==N_SHARDS,"RELEASE_100")
  for shard in range(25):
   by_ordinal=collections.defaultdict(list)
   for segment in range(1,5):
    e=entries[(segment,shard)]
    cipher=(market/e["ENCRYPTED_ASSET_NAME"]).read_bytes()
    need(digest(cipher)==e["ENCRYPTED_ASSET_SHA256"],"CIPHERTEXT_SHA")
    raw=decrypt_synthetic_package(cipher,private_key=key)
    need(digest(raw)==e["PLAINTEXT_CANONICAL_SHA256"],"PLAINTEXT_SHA")
    batch=json.loads(raw)
    need(batch["schema"]=="mxm.v4.shallow-m5-v2.raw-shard.v1" and
         batch["segment_index"]==segment and batch["shard_index"]==shard and
         batch["identity_range"]==e["IDENTITY_RANGE"],"SOURCE_IDENTITY")
    count=0
    for item in batch["items"]:
     rr=item["rows"];count+=len(rr)
     by_ordinal[item["ordinal"]].extend(rr)
    need(count==e["ROW_COUNT"],"ROWS_PER_SHARD")
    result["original_shards"]+=1;result["original_rows"]+=count
   for ordinal in sorted(by_ordinal):
    result["identities"]+=1
    rows=parse(by_ordinal[ordinal])
    proposed,invalid=candidates(rows)
    result["invalid_tick_volume_bars"]+=invalid
    result["input_only_candidates"]+=len(proposed)
    observed=result_for(rows,proposed)
    for entry,side,gross in observed:
     if gross is None:
      result["right_censored"]+=1;continue
     result["complete_proxy_exits"]+=1
     result["gross_bps_sum"]+=gross
     result["scenario_after_10bps_sum"]+=gross-10
     result["scenario_after_20bps_sum"]+=gross-20
     week=dt.datetime.fromtimestamp(entry,dt.timezone.utc).strftime("%G-W%V")
     result["weekly_proxies"][week]=result["weekly_proxies"].get(week,0)+1
     private.append({"ordinal":ordinal,"entry":entry,"side":side,"gross_bps":gross})
   print("MXM_BE_VOLUME_FLOW_SHA_VERIFIED_SHARD",shard,flush=True)
  need(result["original_shards"]==N_SHARDS and result["original_rows"]==ROWS
       and result["identities"]==NAMES,"ALL_1576_AUTHENTICATED")
  pubkey=env.ROOT/"research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem"
  need(public_spki_sha256(pubkey)==fp,"PUBLIC_RECIPIENT")
  OUT.mkdir(parents=True,exist_ok=False)
  confidential=json.dumps(private,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
  encrypt_shard(confidential,public_key=pubkey,output=OUT/"individual.mxmenc")
  result["encrypted_ledger_sha256"]=digest((OUT/"individual.mxmenc").read_bytes())
  result["complete_mean_gross_bps"]=round(result["gross_bps_sum"]/result["complete_proxy_exits"],5) if result["complete_proxy_exits"] else None
  result["candidate_density_per_full_iso_week_is_not_hard21"]=True
  (OUT/"public.json").write_text(json.dumps(result,sort_keys=True,allow_nan=False,separators=(",",":"))+"\n")
  print("MXM_BE_VOLUME_FLOW_FIRST_AUTHENTIC "+json.dumps(result,sort_keys=True,allow_nan=False),flush=True)

if __name__=="__main__":
 import sys
 need(sys.argv[1:] in (["selftest"],["protected"]),"ARGS")
 selftest() if sys.argv[1:]==["selftest"] else authentic()
