"""Prospective repair: authentic request ledger, partial continuation, broad universe."""
import os,json,pathlib,tempfile,time,base64,re,subprocess,gzip
from datetime import datetime,timezone
from collections import Counter
from . import storage_v2 as storage,archive_v2 as ar
from .storage_diagnostics_v3 import DiagnosticRotatingStore
from .preserve_stop_v2 import api,complete_assets
from research_core_v4.full_native_frontier_20261014_v1 import runner_v1 as v1
from research_core_v4.cost_frequency_discovery_v1.collector_v1 import Collector
from research_core_v4 import shallow_m5_support_v2 as protocol
from m6.cost_evidence import decode_ctrader_tick_page
E=v1.E;need=v1.need;encode=v1.encode;OLD_RELEASE=412634211;OLD_RUN=38555928258
P="research_core_v4/critical_frontier_repair_20261014_v2/"
WF=".github/workflows/mxm-native-frontier-repaired-20261014-v2.yml"
def gate():
 head=os.environ["GITHUB_SHA"];auth=json.loads((E.a.ROOT/(P+"REPAIR_AUTHORITY_V2.json")).read_text())
 need(os.environ["GITHUB_RUN_ATTEMPT"]=="1","NO_UNCONTROLLED_RERUN")
 need(os.environ["GITHUB_WORKFLOW_REF"]==E.w.old.REPO+"/"+WF+"@refs/heads/"+E.w.old.BRANCH,"WORKFLOW_SCOPE")
 need(datetime.now(timezone.utc).isoformat()<auth["expires_utc"],"AUTHORITY_EXPIRED")
 E.a.ancestor(auth["base_head"],head)
 for path,sha in auth["bindings"].items():need(E.w.old.filehash(path)==sha,"REPAIR_SOURCE_BINDING")
 original=json.loads((E.a.ROOT/(v1.P+"EXECUTION_V1.json")).read_text())
 for path,sha in original["bindings"].items():need(E.w.old.filehash(path)==sha,"ORIGINAL_FREEZE")
 need(api("actions/runs/"+str(OLD_RUN))["status"]=="completed","OLD_RUN_STILL_ACTIVE")
 need(api("git/ref/heads/"+E.w.old.BRANCH)["object"]["sha"]==head,"CANONICAL_HEAD_DRIFT")
 return head,{**original,**auth}
def wire_record(db,req,state,sha):
 db.execute("INSERT INTO wire VALUES(?,?,?,?,?,?) ON CONFLICT(s,k,a,b) DO UPDATE SET z=excluded.z,h=excluded.h",(req["s"],req["k"],req["a"],req["b"],state,sha))
def classify_raw(db,req,encoded,more,provenance):
 dec=decode_ctrader_tick_page(encoded)
 need(all(req["a"]<=r.timestamp_ms<=req["b"] for r in dec),"TICK_WINDOW_BINDING")
 ar.tickrows(db,req["s"],req["k"],encoded,req["a"],req["b"])
 if more:
  ar.span(db,req["s"],req["k"],req["a"],req["b"],"PARTIAL_HASMORE")
  if dec:
   low=min(r.timestamp_ms for r in dec)
   ar.span(db,req["s"],req["k"],low,low,"PARTIAL_HASMORE_BOUNDARY_UNRESOLVED")
   ar.span(db,req["s"],req["k"],low+1,req["b"],"CONFIRMED_COMPLETE")
  else:ar.span(db,req["s"],req["k"],req["a"],req["b"],"UNKNOWN_TRANSPORT_EMPTY_HASMORE")
 else:ar.span(db,req["s"],req["k"],req["a"],req["b"],"CONFIRMED_COMPLETE" if dec else "EMPTY_AUTHENTIC_RESPONSE")
 wire_record(db,req,"PARTIAL_HASMORE" if more else "CONFIRMED_COMPLETE" if dec else "EMPTY_AUTHENTIC_RESPONSE",provenance)
def migrate(db,store,a):
 old=v1.FrontierStore(store.head,store.key,store.public,store.tmp,"real");old.release=api("releases/"+str(OLD_RELEASE))
 body=json.loads(old.release["body"])
 need(body["current_journal"]["ciphertext_sha256"]==a["last_safe_checkpoint"]["ciphertext_sha256"],"LAST_SAFE_CHECKPOINT_CHANGED")
 st=v1.restore(db,old);storage.track(db);storage.clear(db)
 print(json.dumps({"phase":"MIGRATING_VERIFIED_CHECKPOINT","generation":st["generation"],"old_processed":st["identity_cursor"]}),flush=True)
 st.update(phase="MIGRATING_ACCEPTED_CHECKPOINT",old_identity_cursor=st["identity_cursor"],identity_cursor=0,repair_version=2,storage_rotation_proof=storage.smoke(store),original_checkpoint={**body["current_journal"],"release_id":OLD_RELEASE})
 for field in ("shards","record_shards"):
  for meta in st.get(field,{}).values():meta["release_id"]=OLD_RELEASE
 for sid,k,lo,hi,z in list(db.execute("SELECT * FROM span")):
  if ar.category(z)=="PARTIAL_HASMORE":
   # Without a raw-page continuation boundary, classify the exact interval as incomplete.
   # It stays missing; the request ledger prevents automatic resend of the same request.
   wire_record(db,{"s":sid,"k":k,"a":lo,"b":hi},"LEGACY_PARTIAL_RAW_BOUNDARY_PENDING",None)
 raw_receipts=0
 old_assets=complete_assets(OLD_RELEASE)
 for asset in old_assets:
  if not (asset["name"].startswith("quotes-op-") and asset["name"].endswith(".mxmenc")):continue
  raw=ar.read_raw(store.key,E.w.old.FP,store.tmp,asset,asset["digest"].removeprefix("sha256:"))
  obj=E.w.old.crypto.strict_json(raw)
  need(obj.get("schema")=="mxm.native.quote.increment.raw.responses.v1","ACCEPTED_RAW_QUOTE_SCHEMA")
  for rec in obj["requests"]:
   req=rec["request"]
   if "encoded" in rec:
    classify_raw(db,req,rec["encoded"],bool(rec["hasMore"]),E.a.sha(raw))
   elif rec.get("state")=="PROVIDER_ERROR":
    ar.span(db,req["s"],req["k"],req["a"],req["b"],"PROVIDER_ERROR_"+rec["provider_code"])
    wire_record(db,req,"PROVIDER_ERROR",E.a.sha(raw))
   else:
    ar.span(db,req["s"],req["k"],req["a"],req["b"],"UNKNOWN_TRANSPORT")
    wire_record(db,req,"UNKNOWN_TRANSPORT",E.a.sha(raw))
   raw_receipts+=1
  if raw_receipts%256==0:print(json.dumps({"phase":"RECONCILING_DURABLE_NATIVE_RESPONSES","receipts":raw_receipts}),flush=True)
 # A before-request batch is not proof of dispatch. Only durable raw responses clear uncertainty.
 unresolved=[]
 for req in st.get("uncertain_wire",[]):
  row=db.execute("SELECT z FROM wire WHERE s=? AND k=? AND a=? AND b=?",(req["s"],req["k"],req["a"],req["b"])).fetchone()
  if row is None or row[0]=="LEGACY_PARTIAL_RAW_BOUNDARY_PENDING":
   ar.span(db,req["s"],req["k"],req["a"],req["b"],"UNCERTAIN_WIRE");unresolved.append(req)
 st["uncertain_wire"]=unresolved;st["pending_requests"]=[]
 known=st["archive"]["asset_receipts"];repair_candidates={x["asset_id"] for x in known if x.get("counts",{}).get("quotes",0)>0}
 seen=({x["asset_id"] for x in known if "asset_id" in x}-repair_candidates)|{asset["id"] for asset in old_assets}
 extra={x["release_id"] for x in known if "release_id" in x}
 supplement=ar.global_reconcile(db,store.key,E.w.old.FP,store.tmp,E.a.ROOT,seen,extra)
 st["archive"]["asset_receipts"].extend(supplement["asset_receipts"]);st["legacy_supplement"]=supplement
 st["repair_reconciliation"]={"old_processed":st["old_identity_cursor"],"old_complete_intervals_not_reissued":True,"raw_receipts_reconciled":raw_receipts,"uncertain_wire_remaining":len(unresolved),"partial_not_complete":True,"legacy_scan":"UNTIL_EMPTY_OR_SHORT_PAGE_NO_FIXED_LIMIT"}
 # Current-proxy calendars cannot prove historical session closure.
 st["historical_session_closure_authority"]="UNAVAILABLE_NO_EMPTY_RESPONSE_RECLASSIFIED_AS_SESSION_CLOSED"
 st["increments_v2"]=[];st["phase"]="REPAIR_VERIFIED_READY_FOR_COLD_RESUME"
 storage.compact(db,store,st);storage.clear(db)
 storage.persist(db,store,st,"migration")
 return st
def check_new_request(db,req):
 row=db.execute("SELECT z FROM wire WHERE s=? AND k=? AND a=? AND b=?",(req["s"],req["k"],req["a"],req["b"])).fetchone()
 if row:
  ar.span(db,req["s"],req["k"],req["a"],req["b"],"UNSAMPLED_OR_UNAVAILABLE")
  return False
 return True
def quote_ops(db,keys):
 by={}
 for sid,t in keys:
  for side in ("bid","ask"):
   by.setdefault((sid,side),[]).append(((t-1800)*1000,t*1000))
 ops=[]
 for (sid,side),ranges in sorted(by.items()):
  merged=[]
  for lo,hi in sorted(ranges):
   if merged and lo<=merged[-1][1]+1:merged[-1]=(merged[-1][0],max(hi,merged[-1][1]))
   else:merged.append((lo,hi))
  for lo,hi in merged:
   for a,b in ar.actionable(db,sid,side,lo,hi):
    req={"s":sid,"k":side,"a":a,"b":b}
    if check_new_request(db,req):ops.append(req)
 return ops
def acquire_quotes(db,keys,col,st,store,deadline):
 while True:
  ops=quote_ops(db,keys)
  if not ops:return True
  if time.monotonic()>deadline:return False
  batch=ops[:16]
  need(st["requests"]["BID_ASK"]+len(batch)<=st["campaign_tick_cap"],"FINITE_CAMPAIGN_TICK_CAP")
  st["op_counter"]+=1;st["pending_requests"]=batch
  storage.persist(db,store,st,"before-quotes-"+str(st["op_counter"]))
  raw=[];error=None;sent=0
  for request in batch:
   if time.monotonic()>deadline:break
   try:
    q=v1.m.ProtoOAGetTickDataReq(ctidTraderAccountId=col.aid,symbolId=request["s"],type=v1.enums.BID if request["k"]=="bid" else v1.enums.ASK,fromTimestamp=request["a"],toTimestamp=request["b"])
    st["requests"]["BID_ASK"]+=1;sent+=1;res=col.send(q,True)
    if isinstance(res,v1.m.ProtoOAErrorRes):
     code=res.errorCode;ar.span(db,request["s"],request["k"],request["a"],request["b"],"PROVIDER_ERROR_"+code);wire_record(db,request,"PROVIDER_ERROR_"+code,None)
     raw.append({"request":request,"state":"PROVIDER_ERROR","provider_code":code})
     if code in ("CH_ACCESS_TOKEN_INVALID","OA_AUTH_TOKEN_EXPIRED","ACCOUNT_NOT_AUTHORIZED","TOO_MANY_REQUESTS"):error="BROKER_"+code;break
     continue
    need(isinstance(res,v1.m.ProtoOAGetTickDataRes) and res.IsInitialized() and res.ctidTraderAccountId==col.aid,"QUOTE_RESPONSE_BINDING")
    enc=[{"timestamp":int(x.timestamp),"tick":int(x.tick)} for x in res.tickData]
    rr=res.SerializeToString();classify_raw(db,request,enc,bool(res.hasMore),E.a.sha(rr))
    raw.append({"request":request,"response_b64":base64.b64encode(rr).decode(),"encoded":enc,"hasMore":bool(res.hasMore)})
   except Exception as exc:
    ar.span(db,request["s"],request["k"],request["a"],request["b"],"UNKNOWN_TRANSPORT")
    wire_record(db,request,"UNKNOWN_TRANSPORT",None)
    raw.append({"request":request,"state":"UNKNOWN_TRANSPORT","exception_class":type(exc).__name__})
    error="TRANSPORT_OR_PROTOCOL_STOP_NO_INFINITE_RETRY";break
  st["_raw"]=raw;st["pending_requests"]=[]
  storage.persist(db,store,st,"after-quotes-"+str(st["op_counter"]))
  if error:raise RuntimeError(error)
  if sent<len(batch):return False
def acquire_m5(db,sid,f,col,st,store,deadline):
 while True:
  gaps=ar.actionable(db,sid,"M5",ar.LOW*1000,ar.END*1000-1)
  if not gaps:return True,[],set()
  if time.monotonic()>deadline:return False,[],set()
  lo,hi=gaps[0];hi=min(hi,lo+7*86400000-1)
  req={"s":sid,"k":"M5","a":lo,"b":hi}
  if not check_new_request(db,req):continue
  need(st["requests"]["M5"]<st["campaign_m5_cap"],"FINITE_CAMPAIGN_M5_CAP")
  st["op_counter"]+=1;st["pending_requests"]=[req];storage.persist(db,store,st,"before-m5-"+str(st["op_counter"]))
  raw=[];error=None
  try:
   q=v1.m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=col.aid,symbolId=sid,period=v1.enums.M5,count=5000,fromTimestamp=lo,toTimestamp=hi)
   st["requests"]["M5"]+=1;res=col.send(q,True)
   if isinstance(res,v1.m.ProtoOAErrorRes):
    ar.span(db,sid,"M5",lo,hi,"PROVIDER_ERROR_"+res.errorCode);wire_record(db,req,"PROVIDER_ERROR_"+res.errorCode,None)
    raw=[{"request":req,"state":"PROVIDER_ERROR","provider_code":res.errorCode}]
   else:
    envelope=col.tr.last_history_envelope
    need(envelope is not None and int(envelope.payloadType)==protocol.PROTO_OA_GET_TRENDBARS_RES_PAYLOAD_TYPE,"M5_RAW_ENVELOPE")
    res=protocol.ProtoOAGetTrendbarsResV2.FromString(envelope.payload)
    need(res.IsInitialized() and res.ctidTraderAccountId==col.aid and res.period==v1.enums.M5 and (not res.HasField("symbolId") or res.symbolId==sid),"M5_RESPONSE_BINDING")
    bars=[protocol.decode_trendbar(protocol.ProtoOATrendbarV2.FromString(b.SerializeToString()),digits=int(f["digits"]),segment_from_ms=0,segment_to_ms=hi) for b in res.trendbar]
    tt=[ar.ts(b["time_utc"])*1000 for b in bars]
    need(len(tt)==len(set(tt)) and all(t%300000==0 and t<=hi for t in tt),"M5_RESPONSE_GRID")
    for t,b in zip(tt,bars):
     if lo<=t<=hi:ar.putbar(db,sid,t//1000,[b[n] for n in ("open","high","low","close","tick_volume")])
    present=res.HasField("hasMore");more=bool(res.hasMore) if present else None
    state="CONFIRMED_COMPLETE" if present and not more else "PARTIAL_HASMORE" if present and more else "UNKNOWN_TRANSPORT_HASMORE_FIELD_ABSENT"
    if state=="CONFIRMED_COMPLETE" and not bars:state="EMPTY_AUTHENTIC_RESPONSE"
    ar.span(db,sid,"M5",lo,hi,state)
    if present and more and tt:
     low=min(tt);ar.span(db,sid,"M5",max(lo,low),hi,"CONFIRMED_COMPLETE")
    digest=E.a.sha(envelope.SerializeToString());wire_record(db,req,state,digest)
    raw=[{"request":req,"response_envelope_b64":base64.b64encode(envelope.SerializeToString()).decode(),"has_more_present":present,"has_more":more,"rows_in_scope":sum(lo<=t<=hi for t in tt)}]
  except Exception as exc:
   ar.span(db,sid,"M5",lo,hi,"UNKNOWN_TRANSPORT");wire_record(db,req,"UNKNOWN_TRANSPORT",None);raw=[{"request":req,"state":"UNKNOWN_TRANSPORT","exception_class":type(exc).__name__}];error="M5_TRANSPORT_OR_PROTOCOL_STOP"
  st["_raw"]=raw;st["pending_requests"]=[];storage.persist(db,store,st,"after-m5-"+str(st["op_counter"]))
  if error:raise RuntimeError(error)
ORIGINAL_QPOINT=v1.qpoint
def covered_qpoint(db,sid,t,strict=False):
 z=ORIGINAL_QPOINT(db,sid,t,strict)
 if z.get("valid"):
  for side in ("bid","ask"):
   if ar.missing(db,sid,side,z[side+"_time_ms"],t*1000):
    z={**z,"valid":False,"state":"INCOMPLETE_AUTHENTIC_QUOTE_COVERAGE","cause":"PARTIAL_UNKNOWN_OR_UNCERTAIN_WIRE_BETWEEN_SEED_AND_BOUNDARY"};break
 return z
def configure():
 v1.ar=ar;v1.persist=storage.persist;v1.acquire_m5=acquire_m5;v1.acquire_quotes=acquire_quotes;v1.qpoint=covered_qpoint
def verify_cold(db,st,store):
 summary={"state":"INDEPENDENT_COLD_RESUME_VERIFIED","generation":st["generation"],"bars":db.execute("SELECT count(*) FROM bar").fetchone()[0],"ticks":db.execute("SELECT count(*) FROM tick").fetchone()[0],"wire":db.execute("SELECT count(*) FROM wire").fetchone()[0],"coverage_states":ar.proof_table(db),"storage_rotation_proof":st["storage_rotation_proof"],"uncertain_wire":len(st["uncertain_wire"]),"requests":st["requests"],"orders":0,"HARD21":False,"alpha_certified":False}
 st["cold_verify_summary"]=summary;st["phase"]="VERIFIED_COLD_RESUME_READY_FOR_NATIVE_WORK";storage.persist(db,store,st,"cold-verify");print(json.dumps(summary),flush=True)
def final(db,st,store):
 records=[e for r in st["identity_records"].values() for e in r.get("events",[])]
 value={"schema":"mxm.repaired.native.frontier.final.v2","source_head":store.head,"generation":st["generation"],"classified_identities":st["identity_cursor"],"identities_total":len(st["eligible"]),"coverage_states":ar.proof_table(db),"uncertain_wire":st["uncertain_wire"],"errors":st["errors"],"repair_reconciliation":st["repair_reconciliation"],"storage_rotation_proof":st["storage_rotation_proof"],"consecutive_ISO_weeks":{w:{"events":sum(e["iso"]==w for e in records),"exante_cost_qualified":sum(e["iso"]==w and e["entry"].get("eligible",False) for e in records)} for w in ("2026-W35","2026-W36","2026-W37")},"candidate_qualification":v1.qualifying(records),"pilot":st["pilot"],"new_requests":st["requests"],"scientific_classification":"DEVELOPMENT_ALREADY_ADAPTIVELY_EXPOSED_NOT_CERTIFICATION","executable_NET":"UNDEMONSTRATED_REFERENCE_QUOTES_NOT_FILLS","HARD21":False,"alpha_certified":False,"actual_orders":0,"cloud_deployment":False,"limitations":"PARTIAL_PROVIDER_UNKNOWN_AND_UNCERTAIN_WINDOWS_REMAIN_EXPLICIT_NO_GLOBAL_ALPHA_OR_AVAILABILITY_CLAIM"}
 meta=store.encrypted(json.loads(encode(value)),"final-economic-classification.mxmenc")
 from cryptography.hazmat.primitives import serialization,hashes
 from cryptography.hazmat.primitives.asymmetric import padding
 signer=serialization.load_pem_private_key(store.key.read_bytes(),password=None);raw=encode(value)
 sig=signer.sign(raw,padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.MAX_LENGTH),hashes.SHA256())
 signed=store.encrypted({"primary":meta,"canonical_sha256":E.a.sha(raw),"signature_b64":base64.b64encode(sig).decode(),"owner_spki_sha256":E.w.old.FP},"final-signed-economic-attestation.mxmenc")
 st["final_report"]=meta;st["final_signature"]=signed;st["phase"]="FINAL_CLASSIFIED_WITH_EXPLICIT_LIMITS";storage.persist(db,store,st,"final")
def main():
 head,a=gate();configure()
 with tempfile.TemporaryDirectory(prefix="mxm-repaired-frontier-",dir=os.environ["RUNNER_TEMP"]) as td:
  tmp=pathlib.Path(td);key,fp=E.w.old._private_key_from_secret(tmp);need(fp==E.w.old.FP,"OWNER_KEY")
  store=DiagnosticRotatingStore(head,key,E.a.ROOT/E.w.old.PUBLIC_KEY,tmp);db=ar.dbopen(tmp/"native.sqlite");storage.track(db)
  body=json.loads(store.anchor["body"])
  if os.environ["GITHUB_JOB"]=="repair":
   if "current_journal" not in body:st=migrate(db,store,a)
   else:st=storage.restore(db,store)
   pathlib.Path(os.environ["GITHUB_OUTPUT"]).open("a").write("ready=true\n");return
  st=storage.restore(db,store)
  if os.environ["GITHUB_JOB"]=="cold_verify":verify_cold(db,st,store);return
  if st["phase"]=="FINAL_CLASSIFIED_WITH_EXPLICIT_LIMITS":pathlib.Path(os.environ["GITHUB_OUTPUT"]).open("a").write("done=true\n");return
  uncertain={tuple(req[n] for n in ("s","k","a","b")) for req in st.get("uncertain_wire",[])}
  reserved=Counter("M5" if req[1]=="M5" else "BID_ASK" for req in uncertain)
  st["wire_uncertainty_budget_reserve"]=dict(reserved)
  st["campaign_tick_cap"]=a["campaign_max_tick_requests"]-reserved["BID_ASK"]
  st["campaign_m5_cap"]=a["campaign_max_m5_requests"]-reserved["M5"]
  st["rows"]={str(s):r for s,r in st["rows"].items()}
  deadline=time.monotonic()+(240 if os.environ["GITHUB_JOB"]=="worker_01" else 1800);col=Collector({"BID_ASK":a["campaign_max_tick_requests"],"M5":a["campaign_max_m5_requests"]})
  st["phase"]="RUNNING_REPAIRED_NATIVE_WORK";failed=None
  try:
   col.connect();need(col.aid==int(st["catalog"]["trader"]["ctidTraderAccountId"]),"SAME_ACCOUNT")
   while st["identity_cursor"]<len(st["eligible"]) and time.monotonic()<deadline:
    sid=st["eligible"][st["identity_cursor"]]
    # Re-evaluate previously processed support only; accepted data and any existing pilot stay frozen.
    if sid not in st.setdefault("v2_revisited",[]):
     if str(sid) in st["identity_records"] and st["pilot"] is None:st["identity_records"][str(sid)]["events"]=[];st.setdefault("_record_dirty_ids",set()).add(sid)
     st["v2_revisited"].append(sid)
    if not v1.process_identity(db,sid,st,col,store,a,deadline):break
    st["identity_cursor"]+=1;st.setdefault("_record_dirty_ids",set()).add(sid);v1.pilot(db,st,store,a)
    storage.persist(db,store,st,"identity-"+str(st["identity_cursor"]))
  except Exception as exc:
   failed=str(exc) if re.fullmatch("[A-Z0-9_]{1,100}",str(exc)) else type(exc).__name__
   st["errors"].append({"run":int(os.environ["GITHUB_RUN_ID"]),"job":os.environ["GITHUB_JOB"],"cause":failed});st["phase"]="STOP_EXPLICIT_OPERATIONAL_LIMIT"
  finally:
   col.close();storage.persist(db,store,st,"worker-end")
  done=st["identity_cursor"]==len(st["eligible"])
  if done:final(db,st,store)
  pathlib.Path(os.environ["GITHUB_OUTPUT"]).open("a").write("done="+str(done).lower()+"\n")
  if failed:raise RuntimeError(failed)
if __name__=="__main__":
 try:main()
 except Exception as exc:
  cause=str(exc) if re.fullmatch("[A-Z0-9_]{1,100}",str(exc)) else type(exc).__name__
  print("FAIL_CLOSED_REPAIRED_FRONTIER_"+cause,flush=True);raise SystemExit(1) from None

