"""MASTER1576 exact frozen gross-coupling DEVELOPMENT reducer.

Production and fabricated routes use the SAME consume_shard / finish code. No
broker, no fitting or lag/symbol selection. Private output is never a Git blob.
"""
import collections
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from research_core_v4 import master1576_screen_v2 as canonical
from research_core_v4.existing1576_data_first_v1 import coupling_response_kernel_v1 as frozen

START = int(datetime(2026,8,20,tzinfo=timezone.utc).timestamp())
END = START+28*86400
LAGS = (0,300,900)
CLOCKS = 672
MASTER = 1576
SEGMENT_BARS = 2016
EXPECTED_ROWS = 3355389
DESIGN_SHA = "762653a589a8893b6f58ad0675f016fb3361baa78d629946bda787355779c3f9"
KERNEL_SHA = "d267fdf4f9fe99c748ca3f4f56132c061ea665805b7968f9c8460249ba468645"
MANIFEST_SHA = "cc28c61a7788fc9d18bd54a343bc0e2c7467b27f1dbb111bf54185f9f0f16cb4"
REASON = ("SUPPORTED","FEATURE_GAP","FEATURE_RECEIPT","ZERO_ACTIVITY",
          "COMMON_ZERO_DIRECTION_ABSTENTION","LABEL_GAP","LABEL_RECEIPT",
          "DOMAIN_CENSOR")
class NumericalStop(Exception):
    pass
def require(ok, code):
    if not ok:raise NumericalStop(code)
def enc(x):
    return (json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def metrics():
    return {"n":0,"sum":[0.0]*3,"cross":[[0.0]*3 for _ in range(3)],
            "agreement":0,"disagreement":0,"reasons":{k:0 for k in REASON}}
def tally(m,values,a,b,reason):
    require(reason in REASON,"UNEXPECTED_REASON")
    m["reasons"][reason]+=1
    if values is None:return
    m["n"]+=1
    for j in range(3):
        m["sum"][j]+=values[j]
        for k in range(3):m["cross"][j][k]+=values[j]*values[k]
    m["agreement"]+=int(a==b);m["disagreement"]+=int(a!=b)
def state(ordinal,symbol,context):
    return {"ordinal":ordinal,"symbol_id":symbol,"context":context,
            "last":-1,"rows":0,"next_clock":0,"buffer":{},
            "lag":{str(l):metrics() for l in LAGS},
            "weekly":[{str(l):metrics() for l in LAGS} for _ in range(4)]}
def new(master):
    require(len(master)==MASTER,"MASTER_SIZE")
    require([x["symbol_id"] for x in master]==sorted({x["symbol_id"] for x in master}),"MASTER_ORDER")
    return {"schema":"mxm.numeric.streaming.state.v1","next_shard":0,"rows":0,
            "states":[state(i+1,m["symbol_id"],m.get("asset_class","UNKNOWN")) for i,m in enumerate(master)],
            "clock_vectors":{str(l):[[0.,0.,0.] for _ in range(CLOCKS)] for l in LAGS},
            "crosslag_delta":{"n":0,"sum":[0.]*3,"cross":[[0.]*3 for _ in range(3)]}}
def _bar(row,digits):
    require(isinstance(row,dict) and set(row)==canonical.ROW_KEYS,"ROW_SCHEMA")
    ts=canonical.timestamp(row["time_utc"])
    require(START<=ts<END and (ts-START)%300==0,"ROW_TIME_DOMAIN")
    vals={}
    for key in ("open","high","low","close"):
        value=row[key]
        require(type(value) is str and re.fullmatch(r"-?\d+(?:\.\d+)?",value)!=None,"OHLC_TEXT")
        try:d=Decimal(value)
        except InvalidOperation:raise NumericalStop("INVALID_DECIMAL") from None
        require(d.is_finite() and format(abs(d) if d==0 else d,f".{digits}f")==value,"OHLC_DIGITS")
        vals[key]=d
    o,h,l,c=(vals[k] for k in ("open","high","low","close"))
    require(0<l<=min(o,c)<=max(o,c)<=h,"INVALID_OHLC")
    v=row["tick_volume"]
    require(type(v) is str and re.fullmatch(r"0|[1-9]\d*",v)!=None,"INVALID_VOLUME")
    return ts,{"timestamp":ts,"available_at":ts+300,"open":float(o),
               "high":float(h),"low":float(l),"close":float(c),"tick_volume":int(v)}
def _advance(engine,s,through):
    """Score each clock once after worst-case response maturity; trim only after."""
    while s["next_clock"]<CLOCKS:
        j=s["next_clock"];t=START+j*3600
        if t+3600+max(LAGS)>through:break
        buf={int(k):v for k,v in s["buffer"].items()}
        paired=[]
        for lag in LAGS:
            # These calls ARE the unchanged accepted mathematical implementation.
            dr,why=frozen.directions(buf,t,lag)
            if dr is None:
                value=None;reason=why
            else:
                y,why=frozen.response(buf,t,lag,t+3600+lag,END)
                if y is None:value=None;reason=why
                else:
                    a,b=dr
                    value=[a*y*10000,b*y*10000,(a-b)*y*10000]
                    require(all(math.isfinite(x) for x in value),"NONFINITE_RESPONSE")
                    reason="SUPPORTED"
            key=str(lag)
            tally(s["lag"][key],value,*dr if dr is not None else (0,0),reason)
            tally(s["weekly"][j//168][key],value,*dr if dr is not None else (0,0),reason)
            if value is not None:
                for k in range(3):engine["clock_vectors"][key][j][k]+=value[k]
            paired.append(value)
        if all(x is not None for x in paired):
            v=[x[2] for x in paired];cross=engine["crosslag_delta"];cross["n"]+=1
            for k in range(3):
                cross["sum"][k]+=v[k]
                for p in range(3):cross["cross"][k][p]+=v[k]*v[p]
        s["next_clock"]+=1
        # q=t-lag => oldest feature = t-7200; retain this prefix for next clock.
        retain=START+s["next_clock"]*3600-7200
        s["buffer"]={k:v for k,v in s["buffer"].items() if int(k)>=retain}
def _feed(engine,s,ts,bar):
    require(ts>s["last"],"DUPLICATE_OR_UNORDERED_ROW")
    s["buffer"][str(ts)]=bar;s["last"]=ts;s["rows"]+=1
    _advance(engine,s,ts+300)
    require(len(s["buffer"])<=96,"ROLLING_MEMORY_LIMIT")
def consume_shard(engine,raw,entry,master,digits, *, ciphertext=None):
    """Exact canonical source/ordinal/segment validation and numeric streaming."""
    idx=engine["next_shard"];require(idx<100,"EXTRA_SHARD")
    seg=idx//25+1;shard=idx%25
    require((entry["SEGMENT_INDEX"],entry["SHARD_INDEX"])==(seg,shard),"SHARD_ORDER")
    if ciphertext is not None:
        require(sha(ciphertext)==entry["ENCRYPTED_ASSET_SHA256"],"CIPHERTEXT_DIGEST")
    require(type(raw) is bytes and sha(raw)==entry["PLAINTEXT_CANONICAL_SHA256"],"PLAINTEXT_DIGEST")
    obj=canonical.strict_json(raw)
    require(canonical.canonical(obj)==raw,"NONCANONICAL_INPUT")
    lo=shard*64+1;hi=min(MASTER,lo+63)
    require(set(obj)==canonical.PACKAGE_KEYS and obj["schema"]=="mxm.v4.shallow-m5-v2.raw-shard.v1","PACKAGE_SCHEMA")
    require(obj["segment_index"]==seg and obj["shard_index"]==shard and
            obj["identity_range"]==entry["IDENTITY_RANGE"]==[lo,hi],"PACKAGE_BINDING")
    require(type(obj["items"]) is list and len(obj["items"])==hi-lo+1,"ITEM_COUNT")
    count=0;requests=0;first=None;last=None
    for ordinal,item in zip(range(lo,hi+1),obj["items"]):
        symbol=master[ordinal-1]["symbol_id"];s=engine["states"][ordinal-1]
        require(set(item)==canonical.ITEM_KEYS and item["ordinal"]==ordinal and
                item["symbol_id"]==symbol and item["failure"] is None and
                item["page_cap_hits"]==0 and item["retry_count"]==0 and
                type(item["request_count"]) is int and item["request_count"]>=1 and
                type(item["transport_geometry_pages"]) is list,"ITEM_BINDING")
        require(item["classification"]==("SHALLOW_SUPPORT_COMPLETE" if item["rows"] else "NO_HISTORICAL_SUPPORT"),"ITEM_CLASS")
        previous=-1
        require(symbol in digits and 0<=digits[symbol]<=15,"DIGITS_BINDING")
        for row in item["rows"]:
            ts,bar=_bar(row,digits[symbol])
            require((ts-START)//(SEGMENT_BARS*300)==seg-1 and ts>previous,"SEGMENT_TIME_ORDER")
            previous=ts
            _feed(engine,s,ts,bar)
            count+=1
            first=min(first or row["time_utc"],row["time_utc"])
            last=max(last or row["time_utc"],row["time_utc"])
        requests+=item["request_count"]
    require(count==entry["ROW_COUNT"] and requests==entry["REQUEST_COUNT"] and
            first==entry["FIRST_TIMESTAMP"] and last==entry["LAST_TIMESTAMP"] and
            entry["RETRY_COUNT"]==0 and entry["PAGE_CAP_HITS"]==0 and
            entry["FAILURE_LEDGER"]=={} and entry["PROTECTED_FORWARD_ROW_COUNT"]==0,"SOURCE_MANIFEST_COUNT")
    engine["rows"]+=count;engine["next_shard"]+=1
    if shard==24:
        # all identity shards for segment complete; advance clocks through exact segment end
        for s in engine["states"]:_advance(engine,s,START+seg*7*86400)
    return count
def _summary(m,denom):
    n=m["n"];v=m["sum"];cross=m["cross"]
    return {"supported":n,"calendar":denom,"fixed_calendar_mean":[x/denom for x in v],
            "supported_mean":[x/n if n else None for x in v],
            "sample_covariance":[[(cross[i][j]-v[i]*v[j]/n)/(n-1) if n>1 else None
                 for j in range(3)] for i in range(3)],
            "agreement":m["agreement"],"disagreement":m["disagreement"],
            "reasons":m["reasons"]}
def _combine(ms):
    o=metrics()
    for m in ms:
        o["n"]+=m["n"];o["agreement"]+=m["agreement"];o["disagreement"]+=m["disagreement"]
        for k in REASON:o["reasons"][k]+=m["reasons"][k]
        for j in range(3):
            o["sum"][j]+=m["sum"][j]
            for k in range(3):o["cross"][j][k]+=m["cross"][j][k]
    return o
def finish(engine,expected_rows=EXPECTED_ROWS):
    require(engine["next_shard"]==100 and engine["rows"]==expected_rows,"INCOMPLETE_SOURCE")
    for s in engine["states"]:_advance(engine,s,END+3600+max(LAGS))
    require(all(s["next_clock"]==CLOCKS for s in engine["states"]),"INCOMPLETE_CLOCKS")
    out={"schema":"mxm.numeric.development.private.report.v1","identities":MASTER,
         "input_shards":100,"rows":engine["rows"],"lags_seconds":list(LAGS),
         "calendar_start": "2026-08-20T00:00:00Z",
         "calendar_end_exclusive":"2026-09-17T00:00:00Z",
         "full_frontier":{},"four_weeks":{},"native_contexts":{},
         "crosslag_delta":engine["crosslag_delta"],
         "hourly_calendar_vectors":engine["clock_vectors"],
         "identity_results":[],"receipt_provenance":"UNKNOWN_CONDITIONAL_LAGS",
         "costs":"COST_UNRESOLVED","claim":"DESCRIPTIVE_GROSS_DEVELOPMENT_ONLY"}
    for lag in LAGS:
        k=str(lag)
        out["full_frontier"][k]=_summary(_combine([s["lag"][k] for s in engine["states"]]),MASTER*CLOCKS)
        out["four_weeks"][k]=[_summary(_combine([s["weekly"][w][k] for s in engine["states"]]),MASTER*168) for w in range(4)]
    for s in engine["states"]:
        out["identity_results"].append({"ordinal":s["ordinal"],"symbol_id":s["symbol_id"],
            "context":s["context"],"rows":s["rows"],
            "lags":{k:_summary(s["lag"][k],CLOCKS) for k in map(str,LAGS)}})
    contexts=sorted({s["context"] for s in engine["states"]})
    for context in contexts:
        subset=[s for s in engine["states"] if s["context"]==context]
        out["native_contexts"][context]={k:_summary(_combine([s["lag"][k] for s in subset]),
                           len(subset)*CLOCKS) for k in map(str,LAGS)}
    return out
