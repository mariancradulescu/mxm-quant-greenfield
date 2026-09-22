from __future__ import annotations
import csv,hashlib,io,json,statistics,zipfile
from collections import Counter
from bisect import bisect_left
from datetime import datetime,timezone,timedelta
from pathlib import Path

VERSION="MXM_COMPETITION_ULTRA_FAST_STAGE_A_FRONTIER_V2_EVALUATOR_V1"
CAP="dd0736c3156abfa057303a9b2a31ef3db36b02d66afc5fa33ddccc7f416f5d3d"
COST_SHA="b7ca6191b5570c1cc22f644feb6b0124c6bec0f00fc5ad5a8c772419bcb481b9"
P="MXM_COMPETITION_ULTRA_FAST_STAGE_A_V6/"
CID="V2-C023"
EXPECTED_SPEC_HASH="c2b8ec06c54743b38168980c7746c50401f563ebee45c55b876654423807b34a"
S=datetime(2026,6,15,tzinfo=timezone.utc)
E=datetime(2026,9,14,tzinfo=timezone.utc)
L4=datetime(2026,8,17,tzinfo=timezone.utc)
M5=timedelta(minutes=5)
N=1000.0
MARKETS=("USDJPY","GBPUSD","USDCHF","AUDUSD","US500","US2000","SpotCrude","SpotBrent","ETHUSD","Copper")
COSTS={
"USDJPY":0.00009897913276463102,
"GBPUSD":0.00008128548006115812,
"USDCHF":0.00010950834729796968,
"AUDUSD":0.00012605282979588124,
"US500":0.00008183348448281017,
"US2000":0.00016431898117880028,
"SpotCrude":0.0004207461369287441,
"SpotBrent":0.0005125182478063144,
"ETHUSD":0.0009165483302819816,
"Copper":0.0005268316490290482,
}
class FrontierIntegrityError(ValueError): pass

def canonical_json(v):
 return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)
def sha_bytes(b): return hashlib.sha256(b).hexdigest()
def sha_file(p): return sha_bytes(Path(p).read_bytes())
def dt(s): return datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(timezone.utc)
def spec_hash(spec):
 return sha_bytes(canonical_json({k:v for k,v in spec.items() if k not in {"rationale","provenance","spec_hash"}}).encode("utf-8"))
def result_hash(result):
 return sha_bytes(canonical_json({k:v for k,v in result.items() if k!="result_hash"}).encode("utf-8"))

def open_capture(path):
 if sha_file(path)!=CAP: raise FrontierIntegrityError("capture SHA mismatch")
 z=zipfile.ZipFile(path)
 bad=z.testzip()
 if bad: raise FrontierIntegrityError("capture CRC failure: "+str(bad))
 checks={x.split("  ",1)[1]:x.split("  ",1)[0] for x in z.read(P+"CHECKSUMS.sha256").decode().splitlines() if x.strip()}
 actual={}
 for name in z.namelist():
  if name.startswith(P) and not name.endswith("/") and not name.endswith("CHECKSUMS.sha256"):
   actual[name[len(P):]]=sha_bytes(z.read(name))
 if checks!=actual: raise FrontierIntegrityError("internal checksum mismatch")
 return z

def read_rows(z,symbol):
 out=[]
 for r in csv.DictReader(io.StringIO(z.read(P+f"stage_a_m5/{symbol}_M5.csv").decode())):
  out.append({"t":dt(r["time_utc"]),"o":float(r["open"]),"h":float(r["high"]),"l":float(r["low"]),"c":float(r["close"])})
 if not out or any(out[i]["t"]>=out[i+1]["t"] for i in range(len(out)-1)):
  raise FrontierIntegrityError(symbol+" chronology")
 return out

def contiguous_history(rows,index,bars=48):
 if index-bars<0: return False
 return all(rows[j+1]["t"]-rows[j]["t"]==M5 for j in range(index-bars,index))

def weeks():
 out=[]; d=S
 while d<E:
  key=f"{d.isocalendar().year}-W{d.isocalendar().week:02d}"
  if key not in out: out.append(key)
  d+=timedelta(days=1)
 return out

def add(bucket,key,g,c,n):
 x=bucket.setdefault(key,{"event_count":0,"gross_pnl_eur":0.0,"transaction_cost_eur":0.0,"coarse_net_pnl_eur":0.0})
 x["event_count"]+=1; x["gross_pnl_eur"]+=g; x["transaction_cost_eur"]+=c; x["coarse_net_pnl_eur"]+=n

def generate_trades(rows_by_symbol):
 maps={s:{r["t"]:i for i,r in enumerate(rows_by_symbol[s])} for s in MARKETS}
 times={s:[r["t"] for r in rows_by_symbol[s]] for s in MARKETS}
 trades=[]; active_until=None; d=S
 while d<E:
  if d.minute==0 and d.second==0 and d.hour in (0,4,8,12,16,20):
   if d+timedelta(hours=4)>E:
    d+=M5; continue
   if active_until is not None and d<active_until:
    d+=M5; continue
   ranked=[]
   signal_open=d-M5
   for s in MARKETS:
    q=rows_by_symbol[s]; m=maps[s]
    i=m.get(signal_open); ei=m.get(d)
    if i is None or ei is None or ei!=i+1 or not contiguous_history(q,i,48):
     continue
    ret=q[i]["c"]/q[i-48]["c"]-1.0
    if ret==0: continue
    ranked.append((abs(ret)/COSTS[s],s,ret,ei))
   if ranked:
    ranked.sort(key=lambda x:(-x[0],x[1]))
    score,s,ret,ei=ranked[0]; q=rows_by_symbol[s]
    exit_intent=d+timedelta(hours=4)
    j=bisect_left(times[s],exit_intent)
    if j<len(q) and q[j]["t"]<E:
     direction="LONG" if ret>0 else "SHORT"
     trades.append({"s":s,"d":direction,"e":d,"x":q[j]["t"],"p":q[ei]["o"],"q":q[j]["o"],"costf":COSTS[s],"score":score})
     active_until=q[j]["t"]
  d+=M5
 return trades

def evaluate(spec,trades,evaluator_sha):
 if spec.get("id")!=CID or spec_hash(spec)!=EXPECTED_SPEC_HASH or spec.get("spec_hash")!=EXPECTED_SPEC_HASH:
  raise FrontierIntegrityError("candidate spec hash mismatch")
 if not trades: raise FrontierIntegrityError("no evaluable trades")
 W={k:0 for k in weeks()}; wd={k:0 for k in ("MON","TUE","WED","THU","FRI","SAT","SUN")}; ss=Counter()
 sy={}; di={}; sub={}; dates=[]; holds=[]
 gross=cost=net=cum=peak=dd=0.0
 for t in trades:
  sign=1 if t["d"]=="LONG" else -1
  g=((t["q"]-t["p"])/t["p"])*sign*N; c=t["costf"]*N; n=g-c
  gross+=g;cost+=c;net+=n;cum+=n;peak=max(peak,cum);dd=max(dd,peak-cum)
  iso=t["e"].isocalendar(); W[f"{iso.year}-W{iso.week:02d}"]+=1
  wd[("MON","TUE","WED","THU","FRI","SAT","SUN")[t["e"].weekday()]]+=1
  h=(t["e"].hour//3)*3; ss[f"UTC_{h:02d}_{(h+3)%24:02d}"]+=1
  dates.append(t["e"].date()); holds.append((t["x"]-t["e"]).total_seconds()/60.0)
  add(sy,t["s"],g,c,n); add(di,t["d"],g,c,n); add(sub,"LATEST_4W" if t["e"]>=L4 else "EARLY_9W",g,c,n)
 D=sorted(set(dates))
 gaps=[(D[0]-S.date()).days]+[(b-a).days-1 for a,b in zip(D,D[1:])]+[(E.date()-D[-1]).days]
 metrics={
  "event_count":len(trades),"gross_pnl":gross,"coarse_net_pnl":net,
  "gross_return":gross/(len(trades)*N),"coarse_net_return":net/(len(trades)*N),
  "gross_per_event":gross/len(trades),"net_per_event":net/len(trades),
  "cost_burden":cost/(len(trades)*N),"turnover":2*N*len(trades),
  "weekly_events":W,"active_weeks":sum(v>0 for v in W.values()),"longest_inactive_gap":max(gaps),
  "weekday_distribution":wd,"session_distribution":dict(ss),
  "hold_duration":{"min_minutes":min(holds),"median_minutes":statistics.median(holds),"mean_minutes":statistics.mean(holds),"max_minutes":max(holds)},
  "exposure":sum(holds)/((E-S).total_seconds()/60.0),"drawdown":dd,
  "symbol_contribution":sy,"direction_contribution":di,"subperiod_contribution":sub,
  "regime_contribution":{"state":"NOT_APPLICABLE","reason":"No prospectively frozen regime taxonomy in Wave 02."}
 }
 status="GROSS_EDGE_FAIL" if gross<=0 else ("COARSE_NET_FAIL" if net<=0 else "DISCOVERY_SURVIVOR")
 result={
  "candidate_id":CID,"spec_hash":EXPECTED_SPEC_HASH,"stage":"A","status":status,
  "implementation_validity":{"state":"VALID","reason":"Prospectively frozen cross-market four-hour evaluator and accepted V6 integrity gates passed."},
  "metrics":metrics,
  "eur200_feasibility":{"state":"NOT_EVALUATED","reason":"Stage A uses fixed EUR1000 analytic normalization; shared EUR200 replay is required only for a Stage-A survivor and must not synthesize volume or margin."},
  "cost_confidence":{"state":"CONSERVATIVE_BOUND","reason":"Uses the unchanged pre-outcome V6 per-symbol coarse roundtrip cost authority."},
  "data_completeness":{"state":"SUFFICIENT","reason":"Accepted V6 13-week M5 capture with checksum-bound complete Stage-A series."},
  "provenance":{
   "data_evidence":{"identity":"MXM_COMPETITION_ULTRA_FAST_STAGE_A_V6","binding":{"type":"DATASET_SHA256","sha256":CAP}},
   "cost_evidence":{"identity":"COMPETITION_ULTRA_FAST_STAGE_A_COARSE_COST_AUTHORITY_V1","state":"CONSERVATIVE_BOUND","sha256":COST_SHA},
   "evaluator":{"version":VERSION,"sha256":evaluator_sha}
  }
 }
 result["result_hash"]=result_hash(result)
 return result

def execute(spec_path,capture_zip,evaluator_path=None):
 spec=json.loads(Path(spec_path).read_text())
 z=open_capture(capture_zip)
 rows={s:read_rows(z,s) for s in MARKETS}
 trades=generate_trades(rows)
 evaluator_sha=sha_file(evaluator_path or __file__)
 result=evaluate(spec,trades,evaluator_sha)
 W=result["metrics"]["weekly_events"]
 summary={
  "schema":"mxm.greenfield.v2.competition-ultra-fast-economic-wave-02-stage-a-summary.v1",
  "candidate_id":CID,"capture_sha256":CAP,"cost_authority_sha256":COST_SHA,
  "result":{"status":result["status"],"event_count":result["metrics"]["event_count"],"gross_pnl":result["metrics"]["gross_pnl"],
            "transaction_cost_eur":sum(v["transaction_cost_eur"] for v in result["metrics"]["symbol_contribution"].values()),
            "coarse_net_pnl":result["metrics"]["coarse_net_pnl"],"net_per_event":result["metrics"]["net_per_event"],
            "drawdown":result["metrics"]["drawdown"],"latest_4w":result["metrics"]["subperiod_contribution"].get("LATEST_4W",{}),
            "result_hash":result["result_hash"]},
  "natural_hard21_stage_a":{
    "meaning":"ANALYTIC_EXECUTED_ENTRY_OPPORTUNITIES_NOT_SHARED_EUR200_BROKER_REPLAY",
    "executed_entries_by_week":W,"weeks_ge_21":sum(v>=21 for v in W.values()),"weeks_lt_21":sum(v<21 for v in W.values()),
    "worst_deficit":max(0,21-min(W.values())),"minimum_entries_week":min(W.values()),"maximum_entries_week":max(W.values())
  },
  "shared_eur200":{"state":"NOT_EVALUATED","reason":"No Stage-B shared-account replay is performed unless this identity is a Stage-A survivor."},
  "protected_evidence_opened":False
 }
 return result,summary

if __name__=="__main__":
 import argparse
 ap=argparse.ArgumentParser()
 ap.add_argument("--spec",required=True);ap.add_argument("--capture",required=True);ap.add_argument("--result-out",required=True);ap.add_argument("--summary-out",required=True)
 a=ap.parse_args()
 r,s=execute(a.spec,a.capture,__file__)
 Path(a.result_out).write_text(json.dumps(r,indent=2,sort_keys=False)+"\n")
 Path(a.summary_out).write_text(json.dumps(s,indent=2,sort_keys=False)+"\n")
 print(json.dumps({"candidate_id":CID,"status":r["status"],"event_count":r["metrics"]["event_count"],"result_hash":r["result_hash"]},sort_keys=True))
