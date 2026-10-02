from __future__ import annotations
import argparse,csv,hashlib,json
from collections import defaultdict
from pathlib import Path
from research_core_v4 import response_evaluator_v3 as ev
from research_core_v4 import development_execution_runner_v1 as runner

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--raw-root",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    authority=runner.load_json(runner.ROOT/runner.AUTHORITY_REL)
    design=runner.load_json(runner.ROOT/runner.DESIGN_REL)
    start=ev.parse_utc(design["development_interval_utc"][0]);end=ev.parse_utc(design["development_interval_utc"][1])
    expected={int(x["symbol_id"]):x for x in authority["bindings"]["development_series"]}
    args.out.mkdir(parents=True,exist_ok=True)
    all_events=[];byctx={}
    for cfg in design["structural_contexts"]:
        events=[]
        for sym,sid in cfg["development_symbols"]:
            bars,_=runner.verify_series_file(args.raw_root/f"{sid}_M5.csv",expected[int(sid)])
            bars=[b for b in bars if start <= b.time <= end]
            events.extend(ev.build_signal_support(bars,cfg["id"],sym,int(sid)))
        byctx[cfg["id"]]=events;all_events.extend(events)
    fields=["context","symbol","symbol_id","week_key","signal_direction","vol_state","full","baseline","full_h3","baseline_h3","full_h6","baseline_h6","full_h12","baseline_h12","full_h48","baseline_h48"]
    files=[]
    for ctx,events in byctx.items():
        g=defaultdict(lambda:{"full":0,"baseline":0,**{f"{a}_h{h}":0 for a in ("full","baseline") for h in ev.HORIZONS}})
        for e in events:
            k=(e.context,e.symbol,e.symbol_id,e.week_key,e.signal_direction,e.vol_state);a=e.arm.lower();g[k][a]+=1
            for i,h in enumerate(ev.HORIZONS):
                if e.path_available[i]:g[k][f"{a}_h{h}"]+=1
        p=args.out/f"V4_SUPPORT_COUNTS_{ctx}_V2.csv"
        with p.open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n");w.writeheader()
            for k in sorted(g):
                row=dict(zip(fields[:6],k));row.update({x:g[k][x] for x in fields[6:]});w.writerow(row)
        files.append({"context":ctx,"data_rows":sum(1 for _ in p.open())-1,"csv_sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
    report={"market_responses_used":False,"future_returns_computed":False,"row_count":len(all_events),"canonical_sha256":ev.skeleton_sha256(all_events),"files":files}
    (args.out/"SUPPORT_REBUILD_V2.json").write_text(json.dumps(report,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
