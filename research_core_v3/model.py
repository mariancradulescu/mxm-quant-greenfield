from __future__ import annotations
import csv,math,zipfile
from dataclasses import dataclass
from datetime import datetime,timezone
from pathlib import Path
from typing import Any,Iterable

@dataclass(frozen=True)
class Bar:
    ts:datetime; open:float; high:float; low:float; close:float; volume:float=0.0
@dataclass(frozen=True)
class Series:
    symbol:str; symbol_id:int|None; source:str; bars:tuple[Bar,...]

def _dt(v):
    d=datetime.fromisoformat(str(v).strip().replace('Z','+00:00'))
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
def _first(row,names):
    low={str(k).lower():v for k,v in row.items()}
    for n in names:
        v=low.get(n.lower())
        if v not in (None,''): return v
    raise KeyError(names)
def _rows(rows,source):
    bars=[]; sym=None; sid=None
    for r in rows:
        try:
            ts=_dt(_first(r,['time_utc','timestamp_utc','timestamp','time','datetime','date']))
            o=float(_first(r,['open','o'])); h=float(_first(r,['high','h'])); l=float(_first(r,['low','l'])); c=float(_first(r,['close','c']))
            try:v=float(_first(r,['tick_volume','volume','vol']))
            except Exception:v=0.0
            if not all(map(math.isfinite,[o,h,l,c,v])) or h<max(o,c) or l>min(o,c) or h<l: continue
            if sym is None:
                try:sym=str(_first(r,['symbol','broker_symbol']))
                except Exception:pass
            if sid is None:
                try:sid=int(_first(r,['symbol_id','id']))
                except Exception:pass
            bars.append(Bar(ts,o,h,l,c,v))
        except Exception: continue
    if not bars:return None
    bars.sort(key=lambda b:b.ts); ded=[]
    for b in bars:
        if ded and b.ts==ded[-1].ts:
            if b!=ded[-1]: raise ValueError('conflicting duplicate timestamp')
            continue
        ded.append(b)
    if sym is None:
        stem=Path(source).stem; p=stem.split('_'); sym='_'.join(p[1:-1]) if len(p)>=3 and p[0].isdigit() else stem
    return Series(sym,sid,source,tuple(ded))
def load_csv(p):
    with p.open('r',encoding='utf-8-sig',newline='') as f:return _rows(csv.DictReader(f),str(p))
def load_zip(p):
    out=[]
    with zipfile.ZipFile(p) as z:
        if 'CAPTURE_MANIFEST.json' in z.namelist() and 'V3_CAPTURE_PAYLOAD.json' in z.namelist():
            from .capture_ingest import load_capture
            return load_capture(p)[0]
        for n in sorted(z.namelist()):
            if not n.lower().endswith('.csv'):continue
            with z.open(n) as raw:
                s=_rows(csv.DictReader((x.decode('utf-8-sig',errors='replace') for x in raw)),f'{p}!{n}')
                if s:out.append(s)
    return out
def discover_series(roots:Iterable[Path]):
    out=[]; seen=set()
    for root in roots:
        if not root.exists():continue
        paths=[root] if root.is_file() else sorted(root.rglob('*'))
        for p in paths:
            try:
                seq=[load_csv(p)] if p.is_file() and p.suffix.lower()=='.csv' else load_zip(p) if p.is_file() and p.suffix.lower()=='.zip' else []
            except (zipfile.BadZipFile,UnicodeError,ValueError):continue
            for s in seq:
                if not s:continue
                k=(s.symbol,s.bars[0].ts,s.bars[-1].ts,len(s.bars))
                if k not in seen: seen.add(k); out.append(s)
    return sorted(out,key=lambda s:(s.symbol,s.source))
