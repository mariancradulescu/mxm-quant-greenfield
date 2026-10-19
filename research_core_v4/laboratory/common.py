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
