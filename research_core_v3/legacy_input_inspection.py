from __future__ import annotations
import base64,gzip,hashlib,json
from pathlib import Path
from typing import Any

OHLC={"open","high","low","close"}
TS={"timestamp","timestamp_utc","time","datetime","date"}

def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def inspect(root:Path)->dict[str,Any]:
    parts=sorted((root/"research_v3/runtime_v2_inputs").glob("CROSS_SECTIONAL_PEER_COHORT_INPUT_V1.part*.b64"))
    if not parts:return {"status":"NOT_PRESENT","parts":0}
    encoded=b"".join(p.read_bytes().strip() for p in parts)
    compressed=base64.b64decode(encoded,validate=True)
    raw=gzip.decompress(compressed)
    report={"schema":"mxm.research-core-v3.legacy-input-inspection.v1","status":"DECODED","parts":len(parts),"encoded_bytes":len(encoded),"compressed_bytes":len(compressed),"uncompressed_bytes":len(raw),"compressed_sha256":sha(compressed),"uncompressed_sha256":sha(raw),"source_parts":[{"path":p.relative_to(root).as_posix(),"sha256":sha(p.read_bytes())} for p in parts]}
    try: doc=json.loads(raw.decode("utf-8")); report["decoded_format"]="JSON"
    except Exception:
        report["decoded_format"]="NON_JSON"; report["prefix_hex"]=raw[:64].hex(); return report
    report["top_level_type"]=type(doc).__name__
    if isinstance(doc,dict):report["top_level_keys"]=sorted(map(str,doc.keys()))
    elif isinstance(doc,list):report["top_level_length"]=len(doc)
    candidates=[]
    def walk(x,path="$"):
        if isinstance(x,list):
            dicts=[v for v in x if isinstance(v,dict)]
            if dicts:
                keys={str(k).lower() for d in dicts[:50] for k in d.keys()}
                if OHLC<=keys and keys&TS:
                    candidates.append({"path":path,"rows":len(dicts),"keys":sorted(keys)})
            for i,v in enumerate(x[:2000]): walk(v,f"{path}[{i}]")
        elif isinstance(x,dict):
            keys={str(k).lower() for k in x.keys()}
            if OHLC<=keys and keys&TS:
                candidates.append({"path":path,"rows":1,"keys":sorted(keys)})
            for k,v in x.items(): walk(v,f"{path}.{k}")
    walk(doc)
    grouped={}
    for c in candidates:
        sig=(tuple(c["keys"]),c["path"].rsplit("[",1)[0])
        g=grouped.setdefault(sig,{"path_prefix":sig[1],"keys":c["keys"],"rows_detected":0})
        g["rows_detected"]+=c["rows"]
    report["ohlc_candidates"]=sorted(grouped.values(),key=lambda x:-x["rows_detected"])[:100]
    report["ohlc_candidate_count"]=len(report["ohlc_candidates"])
    def compact(x,depth=0):
        if depth>3:return type(x).__name__
        if isinstance(x,dict):return {str(k):compact(v,depth+1) for k,v in list(x.items())[:40]}
        if isinstance(x,list):return {"length":len(x),"first":compact(x[0],depth+1) if x else None}
        if isinstance(x,(str,int,float,bool)) or x is None:return x
        return type(x).__name__
    report["structural_sample"]=compact(doc)
    return report
