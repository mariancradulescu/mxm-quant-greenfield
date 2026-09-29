from __future__ import annotations
import hashlib, json, re
from pathlib import Path
from typing import Any

CAPTURE_RE=re.compile(r"capture.*acceptance|acceptance.*capture",re.I)
HASH_KEYS={"sha256","outer_zip_sha256","canonical_payload_sha256","plan_sha256","file_sha256","source_capture_outer_zip_sha256"}

def _sha(path: Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''): h.update(chunk)
    return h.hexdigest()

def _walk(obj: Any, key: str=""):
    if isinstance(obj,dict):
        for k,v in obj.items(): yield from _walk(v,k)
    elif isinstance(obj,list):
        for v in obj: yield from _walk(v,key)
    else: yield key,obj

def build_inventory(root: Path)->dict[str,Any]:
    symbols={}; captures=[]
    for base in [root/'data',root/'evidence',root/'research_v3']:
        if not base.exists(): continue
        for p in sorted(base.rglob('*.json')):
            if 'runtime_v2/' in p.as_posix() or p.stat().st_size>2_500_000: continue
            try: doc=json.loads(p.read_text(encoding='utf-8'))
            except Exception: continue
            rel=p.relative_to(root).as_posix()
            if CAPTURE_RE.search(p.name) or 'source_capture_bundle' in doc or 'capture_acceptance_ref' in json.dumps(list(doc)[:50]):
                hashes={}
                for k,v in _walk(doc):
                    if k in HASH_KEYS and isinstance(v,str): hashes[k]=v
                entry={"ref":rel,"file_sha256":_sha(p),"status":doc.get('status'),"schema":doc.get('schema'),"hashes":hashes}
                for fld in ('source_environment','resolution','interval','frozen_scope','scope','data_coverage','integrity_validation','zero_history_identity'):
                    if fld in doc: entry[fld]=doc[fld]
                captures.append(entry)
            for k,v in _walk(doc):
                if k in ('broker_symbol','symbol') and isinstance(v,str): symbols.setdefault(v,{"symbol":v,"symbol_ids":set(),"source_refs":set()})['source_refs'].add(rel)
            def rec(x):
                if isinstance(x,dict):
                    sym=x.get('broker_symbol') or x.get('symbol'); sid=x.get('symbol_id')
                    if isinstance(sym,str):
                        e=symbols.setdefault(sym,{"symbol":sym,"symbol_ids":set(),"source_refs":set()}); e['source_refs'].add(rel)
                        if isinstance(sid,int): e['symbol_ids'].add(sid)
                    for y in x.values(): rec(y)
                elif isinstance(x,list):
                    for y in x: rec(y)
            rec(doc)
    for e in symbols.values():
        e['symbol_ids']=sorted(e['symbol_ids']); e['source_refs']=sorted(e['source_refs'])
    return {"schema":"mxm.research-core-v3.accepted-data-inventory.v1","authoritative_frontier":1576,"capture_acceptance_documents":captures,"capture_acceptance_count":len(captures),"referenced_symbols":sorted(symbols.values(),key=lambda x:x['symbol']),"referenced_symbol_count":len(symbols),"law":{"structural_representatives_are_not_economic_universe":True,"unsampled_symbols_remain_open":True,"source_only":"Pepperstone cTrader Open API"}}
