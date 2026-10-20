"""Shared integration primitives; no alternate custody, transport or evaluator."""
import hashlib,json,math
from datetime import datetime,timezone
class LabError(ValueError):pass
def need(ok,code):
    if not ok:raise LabError('LAB_'+code)
def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def digest(value):return hashlib.sha256(encoded(value)).hexdigest()
def bytes_digest(value):return hashlib.sha256(value).hexdigest()
def number(v):return type(v) in (int,float) and math.isfinite(v)
def utc_ms(value):
    if type(value) is int:return value
    need(isinstance(value,str),'TIMESTAMP_TYPE')
    d=datetime.fromisoformat(value.replace('Z','+00:00'));need(d.tzinfo is not None,'TIMEZONE_REQUIRED')
    return int(d.astimezone(timezone.utc).timestamp()*1000)

def development_end_ms():
    """One boundary from the original byte-sealed V2 authorities.

    No historical specification, cutoff, counter or data partition is edited.
    Both original authorities must still agree before any reader uses the time.
    """
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    budget=(root/'V2_SEARCH_BUDGET_V1.json').read_bytes()
    wave=(root/'discovery/WAVE_01_V1.json').read_bytes()
    need(bytes_digest(budget)=='6bb57d3c6701108212c348c8a2fa33bdc0efcf6f91c2448639a17eb548c58d86' and
         bytes_digest(wave)=='70f2a42cfbb075f68571da470fd4a3893b78b013b53fc3c256a7cade0de01800',
         'FROZEN_PARTITION_AUTHORITY_CHANGED')
    original=json.loads(budget);declared=json.loads(wave)
    need(original['frozen_utc']==declared['protected_forward_start'],
         'FROZEN_PARTITION_AUTHORITIES_DISAGREE')
    return utc_ms(declared['protected_forward_start'])

DEVELOPMENT_END_MS=development_end_ms()
