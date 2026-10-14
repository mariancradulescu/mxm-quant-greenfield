"""Preserve crypto/storage guards; expose only safe physical error classes."""
import json,urllib.error,re
from .storage_v2 import RotatingStore
def classify(exc,phase):
 chain=[];seen=set();cur=exc
 while cur is not None and id(cur) not in seen and len(chain)<8:
  seen.add(id(cur));chain.append(cur);cur=cur.__cause__ or cur.__context__
 out={"schema":"mxm.safe.storage.physical.error.v1","phase":phase,"exception_classes":[type(x).__name__ for x in chain],"historical_errors_not_reclassified":True}
 for x in chain:
  if isinstance(x,urllib.error.HTTPError):
   out["http_status"]=int(x.code)
   for key in ("X-RateLimit-Limit","X-RateLimit-Remaining","X-RateLimit-Reset","Retry-After"):
    value=x.headers.get(key) if x.headers is not None else None
    if isinstance(value,str) and re.fullmatch("[0-9]{1,16}",value):out[key.lower()]=int(value)
   break
 print(json.dumps(out,sort_keys=True),flush=True)
 return out
class DiagnosticRotatingStore(RotatingStore):
 def encrypted(self,value,name):
  try:return super().encrypted(value,name)
  except Exception as exc:
   info=classify(exc,"ENCRYPTED_UPLOAD_OR_OWNER_READBACK")
   if "http_status" in info:raise RuntimeError("GITHUB_STORAGE_HTTP_"+str(info["http_status"])) from None
   raise
 def restore(self,meta):
  try:return super().restore(meta)
  except Exception as exc:
   classify(exc,"PINNED_OWNER_RESTORE")
   raise
