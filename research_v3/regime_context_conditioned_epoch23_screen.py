"""Prospective non-economic regime conditioned breakout diagnostic."""
import csv
import hashlib
import io
import json
import statistics
import sys
import zipfile
from collections import deque
from datetime import datetime
from pathlib import Path

SOURCE40 = "64ea52126a31c527d2021a50923adab1b7df8f0ce5debe7f631cf4ce09b39503"
SOURCE3 = "d9be18c7aa902a83bad0417bc561b7ef8df4c3ac357ff884d98c4ee3e0cc5d75"
ATR_BARS = 14
PERCENTILE_LOOKBACK = 48
LOW_Q = 0.20
HIGH_Q = 0.80
EVENT_LOOKBACK = 24
EXPANSION = 1.5

def source_rows(path, expected_hash):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash
    with zipfile.ZipFile(path) as z:
        manifest = json.loads(z.read("capture_manifest.json"))
        assert manifest.get("resolution", manifest.get("requested_resolution", "M5")) == "M5"
        series = manifest.get("series", [])
        if series:
            for item in series:
                if item.get("capture_status") != "SERIES_CAPTURE_COMPLETE":
                    continue
                raw = z.read(item["file"])
                assert hashlib.sha256(raw).hexdigest() == item["sha256"]
                yield item["broker_symbol"], raw, False
        else:
            for name in z.namelist():
                if name.startswith("raw/") and name.endswith(".csv"):
                    yield name, z.read(name), True

def parse(raw, canonicalize):
    rows = []
    seen = {}
    for row in csv.DictReader(io.StringIO(raw.decode())):
        t = datetime.fromisoformat(row["time_utc"].replace("Z", "+00:00"))
        values = tuple(float(row[k]) for k in ("open", "high", "low", "close"))
        assert values[1] >= max(values[0], values[3]) and values[2] <= min(values[0], values[3])
        if t in seen:
            assert canonicalize and seen[t] == values, "conflicting duplicate"
            continue
        seen[t] = values
        rows.append((t, *values))
    rows.sort()
    assert all(rows[i][0] > rows[i-1][0] for i in range(1, len(rows)))
    return rows

def percentile_rank(value, window):
    return sum(x <= value for x in window) / len(window)

def one_symbol(rows):
    result = {state: {h: {"events": 0, "valid": 0, "continuation": 0,
                          "reversal": 0, "flat": 0} for h in ("15m", "30m")}
              for state in ("HIGH_VOL_EXPANDING", "LOW_VOL_COMPRESSED")}
    result["UNCLASSIFIED_EVENTS"] = 0
    result["ALL_EVENTS"] = 0
    segment = []
    for row in rows:
        if segment and (row[0] - segment[-1][0]).total_seconds() != 300:
            segment = []
        segment.append(row)
        i = len(segment)-1
        if i < EVENT_LOOKBACK:
            continue
        prior = segment[i-EVENT_LOOKBACK:i]
        current = segment[i]
        median_range = statistics.median(b[2]-b[3] for b in prior)
        current_range = current[2]-current[3]
        expanded = current_range >= EXPANSION*median_range if median_range > 0 else current_range > 0
        direction = (1 if current[4] > max(b[2] for b in prior) else
                     -1 if current[4] < min(b[3] for b in prior) else 0)
        if not expanded or not direction:
            continue
        result["ALL_EVENTS"] += 1
        # ATR values are indexed by bar and require 14 consecutive true ranges.
        # Label t uses ATR(t-1) compared with the 48 ATR values ending at t-2.
        if i < ATR_BARS + PERCENTILE_LOOKBACK + 1:
            result["UNCLASSIFIED_EVENTS"] += 1
            continue
        atr = []
        for j in range(i-PERCENTILE_LOOKBACK-1, i):
            true_ranges = [max(segment[k][2]-segment[k][3],
                               abs(segment[k][2]-segment[k-1][4]),
                               abs(segment[k][3]-segment[k-1][4]))
                           for k in range(j-ATR_BARS+1,j+1)]
            atr.append(sum(true_ranges)/ATR_BARS)
        rank = percentile_rank(atr[-1], atr[:-1])
        state = ("HIGH_VOL_EXPANDING" if rank >= HIGH_Q else
                 "LOW_VOL_COMPRESSED" if rank <= LOW_Q else None)
        if state is None:
            result["UNCLASSIFIED_EVENTS"] += 1
            continue
        # Future values must be evaluated against the original continuous series,
        # so defer follow-through evaluation until the segment is complete.
        result.setdefault("_events", []).append((row[0], direction, state, row[4]))
    by_time = {r[0]: idx for idx,r in enumerate(rows)}
    for t,direction,state,close in result.pop("_events", []):
        idx = by_time[t]
        for h,bars in (("15m",3),("30m",6)):
            a = result[state][h]
            a["events"] += 1
            if idx+bars >= len(rows) or any(
                (rows[k][0]-rows[k-1][0]).total_seconds()!=300
                for k in range(idx+1,idx+bars+1)
            ):
                continue
            a["valid"] += 1
            delta = (rows[idx+bars][4]-close)*direction
            a["continuation" if delta>0 else "reversal" if delta<0 else "flat"] += 1
    return result

def execute(path40, path3, registry_path):
    reps = json.loads(Path(registry_path).read_text())["representatives"]
    ids = {r["symbol_id"]:r["broker_symbol"] for r in reps}
    assert len(ids)==41
    selected = {}
    for name, raw, canonical in source_rows(Path(path40), SOURCE40):
        # Accepted 40-symbol manifest uses exact symbol string.
        if name in ids.values():
            selected[name]=parse(raw, canonical)
    for name, raw, canonical in source_rows(Path(path3), SOURCE3):
        sid=int(name.split("/",1)[1].split("_",1)[0])
        if sid in ids:
            selected[ids[sid]]=parse(raw,canonical)
    assert set(selected)==set(ids.values()), sorted(set(ids.values())-set(selected))
    per = {name:one_symbol(rows) for name,rows in selected.items()}
    agg = {state:{h:{k:sum(v[state][h][k] for v in per.values())
                     for k in ("events","valid","continuation","reversal","flat")}
                  for h in ("15m","30m")}
           for state in ("HIGH_VOL_EXPANDING","LOW_VOL_COMPRESSED")}
    return {"schema":"mxm.greenfield.regime-context-conditioned-structural-screen.v1",
            "status":"DESCRIPTIVE_NON_ECONOMIC_NO_PROMOTION",
            "source_capture_sha256":[SOURCE40,SOURCE3],
            "representatives":41,"params":{"atr_bars":ATR_BARS,"percentile_lookback":PERCENTILE_LOOKBACK,
                "low_rank_at_most":LOW_Q,"high_rank_at_least":HIGH_Q,
                "event_lookback":EVENT_LOOKBACK,"range_expansion_ratio":EXPANSION,
                "horizons_bars":[3,6],"middle_arm":"UNCLASSIFIED"},
            "aggregate":agg,"total_events":sum(v["ALL_EVENTS"] for v in per.values()),
            "unclassified_events":sum(v["UNCLASSIFIED_EVENTS"] for v in per.values()),
            "per_symbol":per,
            "economic_effect":{"v2_attempts":0,"economic_outcomes":0,"protected_forward":False}}

if __name__=="__main__":
    print(json.dumps(execute(*sys.argv[1:4]),indent=2,sort_keys=True))
