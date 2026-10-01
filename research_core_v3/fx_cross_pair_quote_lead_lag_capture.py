"""Frozen 72-cell FX cross-pair quote lead/lag collector with diagnostic-only 15m path fields."""
from __future__ import annotations
import csv, hashlib, json, math, time, zipfile
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from google.protobuf.json_format import MessageToDict
from m6.cost_evidence import BoundaryQuoteIndex, DecodedTick, QUOTE_TYPES, decode_ctrader_tick_page, next_tick_page_to_ms
from m6.ctrader_capture import CaptureContractError, account_fingerprint, atomic_write_json, live_account_candidates, redact_text, require_read_only_request, sha256_file
from m6.ctrader_proto.OpenApiMessages_pb2 import ProtoOAAccountAuthReq, ProtoOAApplicationAuthReq, ProtoOAGetAccountListByAccessTokenReq, ProtoOAGetTickDataReq, ProtoOASymbolsListReq, ProtoOATraderReq
from m6.ctrader_transport import LIVE_HOST, LIVE_PORT, StdlibCTraderTransport

TOOL_VERSION="MXM_V3_FX_CROSS_PAIR_QUOTE_LEAD_LAG_DIAGNOSTIC_CAPTURE_V2"
PLAN_REL="research_core_v3/state/FX_CROSS_PAIR_QUOTE_LEAD_LAG_ACQUISITION_PLAN_V2.json"
DESIGN_REL="research_core_v3/state/FX_CROSS_PAIR_QUOTE_LEAD_LAG_DEVELOPMENT_DESIGN_V1.json"
AUDIT_REL="research_core_v3/state/FX_CROSS_PAIR_QUOTE_LEAD_LAG_PREOUTCOME_AUDIT_V1.json"
DIAG_REL="research_core_v3/state/FX_CROSS_PAIR_QUOTE_LEAD_LAG_PATH_OBSERVABILITY_FREEZE_V1.json"
WORK_REL=".mxm_v3_fx_cross_pair_lead_lag_v2_work"
OUTPUT_REL="fx_lead_lag_output/MXM_V3_FX_CROSS_PAIR_QUOTE_LEAD_LAG_PILOT_EVIDENCE_V2"
TRANSFER_NAME="MXM_V3_FX_CROSS_PAIR_QUOTE_LEAD_LAG_PILOT_EVIDENCE_V2.zip"
ERRORS={"ProtoOAErrorRes","ProtoErrorRes"}

class ExpectedAccountUnavailable(CaptureContractError): pass

def _plain(x):
    return MessageToDict(x,preserving_proto_field_name=False,use_integers_for_enums=True)

def _canon(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def _sha(b): return hashlib.sha256(b).hexdigest()
def _self(doc,key):
    expected=str(doc.get(key) or ""); u=dict(doc); u.pop(key,None)
    if len(expected)!=64 or _sha(_canon(u))!=expected: raise CaptureContractError(f"{key} self-hash mismatch")
def _ms(d,t): return int(datetime.fromisoformat(f"{d}T{t}+00:00").timestamp()*1000)

def _snap(idx,sec):
    try: s=idx.causal_state_at_boundary(sec*1000)
    except CaptureContractError: return None
    if s.bid is None or s.ask is None or s.bid_age_ms is None or s.ask_age_ms is None: return None
    if s.bid_age_ms>2000 or s.ask_age_ms>2000: return None
    b,a=float(s.bid),float(s.ask)
    if not a>=b>0: return None
    return {"bid":b,"ask":a,"mid":(a+b)/2,"spread_bps":math.log(a/b)*10000}

def _path(snaps,entry_sec,direction,horizon=900):
    e=snaps.get(entry_sec)
    if e is None: return {"diagnostic_valid_seconds":0,"diagnostic_expected_seconds":horizon+1,"diagnostic_coverage_fraction":0.0}
    mids=[]; exes=[]
    for sec in range(entry_sec,entry_sec+horizon+1):
        s=snaps.get(sec)
        if s is None: continue
        dt=sec-entry_sec
        mr=direction*math.log(s["mid"]/e["mid"])*10000
        xr=math.log(s["bid"]/e["ask"])*10000 if direction>0 else math.log(e["bid"]/s["ask"])*10000
        mids.append((dt,mr)); exes.append((dt,xr))
    if not mids: return {"diagnostic_valid_seconds":0,"diagnostic_expected_seconds":horizon+1,"diagnostic_coverage_fraction":0.0}
    mm=max(v for _,v in mids); mn=min(v for _,v in mids); xm=max(v for _,v in exes); xn=min(v for _,v in exes)
    return {
      "mid_price_MFE_bps":mm,"mid_price_MAE_bps":max(0.0,-mn),
      "executable_side_aware_MFE_bps":xm,"executable_side_aware_MAE_bps":max(0.0,-xn),
      "time_to_mid_MFE_seconds":min(t for t,v in mids if abs(v-mm)<=1e-12),
      "time_to_first_positive_executable_response_seconds":next((t for t,v in exes if v>0),None),
      "diagnostic_valid_seconds":len(mids),"diagnostic_expected_seconds":horizon+1,
      "diagnostic_coverage_fraction":len(mids)/float(horizon+1)
    }

def offline_preflight(root):
    root=Path(root)
    p=json.loads((root/PLAN_REL).read_text()); d=json.loads((root/DESIGN_REL).read_text()); a=json.loads((root/AUDIT_REL).read_text()); g=json.loads((root/DIAG_REL).read_text())
    for doc,key in ((p,"binding_sha256"),(d,"canonical_sha256"),(a,"canonical_sha256"),(g,"canonical_sha256")): _self(doc,key)
    if p["source_design_sha256"]!=d["canonical_sha256"] or p["source_audit_sha256"]!=a["canonical_sha256"] or p["path_observability_freeze_sha256"]!=g["canonical_sha256"]: raise CaptureContractError("authority binding mismatch")
    if d["test_count"]!=72 or d["parameter_grid"]["holding_seconds"]!=[15,60,180]: raise CaptureContractError("primary 72-cell design changed")
    if p["acquisition"]["base_side_requests_before_pagination"]!=624 or p["acquisition"]["diagnostic_path_horizon_seconds"]!=900: raise CaptureContractError("acquisition geometry changed")
    if p["acquisition"]["fill_authority"] is not False or p["acquisition"]["protected_forward_opened"] is not False or p["broker_identity"]["orders"] is not False: raise CaptureContractError("read-only governance violated")
    return {"primary_tests":72,"relationships":6,"symbols":4,"base_side_requests_before_pagination":624,"diagnostic_horizon_seconds":900}

class LeadLagDiagnosticRunner:
  def __init__(self,client_id,client_secret,access_token,repo_root,progress=print):
    self.root=Path(repo_root); offline_preflight(self.root)
    self.plan=json.loads((self.root/PLAN_REL).read_text()); self.design=json.loads((self.root/DESIGN_REL).read_text()); self.audit=json.loads((self.root/AUDIT_REL).read_text()); self.diag=json.loads((self.root/DIAG_REL).read_text())
    self.client_id=client_id; self.client_secret=client_secret; self.access_token=access_token; self.progress=progress
    self.transport=StdlibCTraderTransport(LIVE_HOST,LIVE_PORT,response_timeout=60)
    self.work=self.root/WORK_REL; self.out=self.root/OUTPUT_REL; self.transfer=self.out.parent/TRANSFER_NAME; self.resume_path=self.work/"resume.json"
    self.last_hist=None; self.hist_requests=0; self.account_evidence={}; self.symbol_evidence={}
    self.relationship={x["relationship_id"]:x for x in self.audit["relationships"]}
    self.work.mkdir(parents=True,exist_ok=True)
    contract={"tool_version":TOOL_VERSION,"plan":self.plan["binding_sha256"],"design":self.design["canonical_sha256"],"diagnostic":self.diag["canonical_sha256"]}
    if self.resume_path.is_file():
      self.resume=json.loads(self.resume_path.read_text())
      if self.resume.get("contract")!=contract: raise CaptureContractError("work folder belongs to a different frozen contract; use a new empty folder")
    else:
      self.resume={"schema":"mxm.research-core-v3.fx-lead-lag-resume.v2","contract":contract,"completed_windows":{}}; atomic_write_json(self.resume_path,self.resume)

  def close(self):
    try:self.transport.close()
    except Exception:pass

  def _send(self,req,historical=False):
    require_read_only_request(type(req).__name__)
    if historical:
      now=time.monotonic()
      if self.last_hist is not None:
        wait=float(self.plan["acquisition"]["request_min_interval_seconds"])-(now-self.last_hist)
        if wait>0: time.sleep(wait)
      self.last_hist=time.monotonic(); self.hist_requests+=1
    r=self.transport.request(req,timeout=60)
    if type(r).__name__ in ERRORS: raise CaptureContractError(f"cTrader API error {getattr(r,'errorCode','UNKNOWN')}: {redact_text(str(getattr(r,'description','') or ''))}")
    return r

  def _auth(self):
    self.progress("[1/4] Verifying frozen Pepperstone LIVE account and exact symbols")
    self._send(ProtoOAApplicationAuthReq(clientId=self.client_id,clientSecret=self.client_secret))
    ar=self._send(ProtoOAGetAccountListByAccessTokenReq(accessToken=self.access_token))
    expected=self.plan["broker_identity"]["accepted_account_fingerprint_sha256"]
    matches=[a for a in live_account_candidates([_plain(x) for x in ar.ctidTraderAccount]) if account_fingerprint(int(a["ctidTraderAccountId"]))==expected]
    if not matches: raise ExpectedAccountUnavailable("frozen account fingerprint absent")
    if len(matches)!=1: raise CaptureContractError("frozen account fingerprint not unique")
    aid=int(matches[0]["ctidTraderAccountId"])
    self._send(ProtoOAAccountAuthReq(ctidTraderAccountId=aid,accessToken=self.access_token))
    tr=_plain(self._send(ProtoOATraderReq(ctidTraderAccountId=aid)).trader); broker=str(tr.get("brokerName") or "")
    if "pepperstone" not in (broker+" "+str(matches[0].get("brokerTitleShort") or "")).lower(): raise CaptureContractError("account is not verifiably Pepperstone")
    sr=self._send(ProtoOASymbolsListReq(ctidTraderAccountId=aid,includeArchivedSymbols=False)); byid={int(x.get("symbolId",0)):x for x in [_plain(s) for s in sr.symbol]}
    for t in self.plan["targets"]:
      row=byid.get(int(t["symbol_id"]))
      if row is None or str(row.get("symbolName") or "")!=t["symbol"] or row.get("enabled") is False: raise CaptureContractError(f"{t['symbol']}: frozen symbol identity unavailable")
      self.symbol_evidence[t["symbol"]]={"symbol":t["symbol"],"symbol_id":int(t["symbol_id"]),"enabled":row.get("enabled")}
    self.account_evidence={"environment":"Pepperstone - Europe LIVE","account_fingerprint_sha256":expected,"broker_name":broker,"raw_account_id_transferred":False}
    self.progress("[ACCOUNT/SYMBOL PASS] No historical request preceded identity verification"); return aid

  def _side(self,aid,target,side,start,end):
    page=end; prev=None; items=[]; pages=0
    while page>=start:
      r=self._send(ProtoOAGetTickDataReq(ctidTraderAccountId=aid,symbolId=int(target["symbol_id"]),type=int(QUOTE_TYPES[side]),fromTimestamp=int(start),toTimestamp=int(page)),historical=True); pages+=1
      dec=decode_ctrader_tick_page([{"timestamp":int(x.timestamp),"tick":int(x.tick)} for x in r.tickData]); items.extend(dec)
      if not bool(getattr(r,"hasMore",False)): break
      if not dec: raise CaptureContractError(f"{target['symbol']} {side}: hasMore with empty page")
      oldest=min(x.timestamp_ms for x in dec); nxt=next_tick_page_to_ms(dec,current_from_ms=start,previous_oldest_ms=prev)
      if nxt is None: break
      prev=oldest
      if nxt>=page: raise CaptureContractError("tick pagination did not progress")
      page=int(nxt)
    seen=set(); out=[]
    for x in sorted(items,key=lambda z:(z.timestamp_ms,z.raw_tick)):
      k=(x.timestamp_ms,x.raw_tick)
      if start<=x.timestamp_ms<=end and k not in seen: seen.add(k); out.append(x)
    return out,{"symbol":target["symbol"],"side":side,"rows":len(out),"pages":pages,"from_ms":start,"to_ms":end}

  def _series(self,ticks,q0,q1):
    snaps={}; bases={}
    for sym,sides in ticks.items():
      idx=BoundaryQuoteIndex(sides["BID"],sides["ASK"]); ss={sec:_snap(idx,sec) for sec in range(q0,q1+1)}; snaps[sym]=ss
      bb={}
      for sec in range(q0+60,q1+1):
        vals=[ss[x]["spread_bps"] for x in range(sec-60,sec) if ss.get(x) is not None]; bb[sec]=median(vals) if len(vals)>=45 else None
      bases[sym]=bb
    return snaps,bases

  def _eval(self,date,start_clock,end_clock,ticks,q0,q1):
    snaps,bases=self._series(ticks,q0,q1); core0=_ms(date,start_clock)//1000; core1=_ms(date,end_clock)//1000; grid=self.design["parameter_grid"]; block={}; cache={}; rows=[]
    for rid in self.design["relationships"]:
      meta=self.relationship[rid]; leader=meta["leader"]; follower=meta["follower"]; sign=int(meta["structural_sign"])
      for L0 in grid["leader_impulse_lookback_seconds"]:
        L=int(L0)
        for sec in range(core0,core1):
          ls,lp,fs,fp=snaps[leader].get(sec),snaps[leader].get(sec-L),snaps[follower].get(sec),snaps[follower].get(sec-L); lb,fb=bases[leader].get(sec),bases[follower].get(sec)
          if any(x is None for x in (ls,lp,fs,fp,lb,fb)) or lb<=0 or fb<=0: continue
          imp=math.log(ls["mid"]/lp["mid"])*10000/lb; lag=abs(math.log(fs["mid"]/fp["mid"])*10000)/fb
          if imp==0 or lag>0.5 or ls["spread_bps"]>lb or fs["spread_bps"]>fb: continue
          direction=(1 if imp>0 else -1)*sign
          for th0 in grid["minimum_abs_leader_impulse_spread_units"]:
            th=float(th0)
            if abs(imp)<th: continue
            for h0 in grid["holding_seconds"]:
              h=int(h0); cid=f"{rid}|L{L}|I{th:g}|H{h}"
              if sec<block.get(cid,-10**18): continue
              ent=sec+1; ex=ent+h; block[cid]=ex; e=snaps[follower].get(ent); x=snaps[follower].get(ex); complete=e is not None and x is not None
              row={"date_utc":date,"window_start_utc":start_clock,"window_end_utc":end_clock,"cell_id":cid,"relationship_id":rid,"leader":leader,"follower":follower,"structural_sign":sign,"lookback_seconds":L,"minimum_abs_leader_impulse_spread_units":th,"holding_seconds":h,"signal_timestamp_utc":datetime.fromtimestamp(sec,tz=timezone.utc).isoformat().replace("+00:00","Z"),"entry_timestamp_utc":datetime.fromtimestamp(ent,tz=timezone.utc).isoformat().replace("+00:00","Z"),"primary_exit_timestamp_utc":datetime.fromtimestamp(ex,tz=timezone.utc).isoformat().replace("+00:00","Z"),"direction":"LONG" if direction>0 else "SHORT","leader_impulse_units":imp,"follower_lag_units":lag,"leader_spread_bps":ls["spread_bps"],"leader_baseline_median_spread_bps":lb,"follower_spread_bps":fs["spread_bps"],"follower_baseline_median_spread_bps":fb,"primary_completed":complete,"primary_censor_reason":"" if complete else ("ENTRY_NOT_FRESH" if e is None else "PRIMARY_EXIT_NOT_FRESH")}
              if e is not None:
                row.update({"entry_bid":e["bid"],"entry_ask":e["ask"],"entry_mid":e["mid"]}); key=(follower,ent,direction)
                if key not in cache: cache[key]=_path(snaps[follower],ent,direction,900)
                row.update(cache[key])
              if complete:
                mid=direction*math.log(x["mid"]/e["mid"])*10000; net=math.log(x["bid"]/e["ask"])*10000 if direction>0 else math.log(e["bid"]/x["ask"])*10000
                row.update({"primary_exit_bid":x["bid"],"primary_exit_ask":x["ask"],"primary_exit_mid":x["mid"],"directional_mid_price_gross_bps":mid,"primary_side_aware_spread_net_bps":net,"exact_execution_drag_bps":mid-net})
              rows.append(row)
    return rows

  def _wpath(self,wid): return self.out/"events"/f"{wid}.csv"
  def _done(self,wid):
    r=self.resume["completed_windows"].get(wid); p=self._wpath(wid)
    return isinstance(r,dict) and p.is_file() and sha256_file(p)==str(r.get("sha256") or "")

  def _write(self,path,rows):
    path.parent.mkdir(parents=True,exist_ok=True); fields=sorted({k for r in rows for k in r}) if rows else ["date_utc","cell_id","primary_completed"]
    with path.open("w",encoding="utf-8",newline="") as f:
      w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n"); w.writeheader()
      for r in rows:w.writerow({k:"" if v is None else v for k,v in r.items()})

  def _capture(self,aid):
    dates=self.plan["calendar"]["dates_utc"]; windows=self.plan["calendar"]["windows_utc"]; total=len(dates)*len(windows); n=0
    self.progress(f"[2/4] {total} untouched core windows | 624 base BID/ASK requests | +900s diagnostic only")
    protected=int(datetime.fromisoformat(self.plan["calendar"]["protected_forward_start_utc"].replace("Z","+00:00")).timestamp()*1000)
    for d in dates:
      for a,b in windows:
        n+=1; wid=f"{d}_{a.replace(':','')}_{b.replace(':','')}"
        if self._done(wid): self.progress(f"[RESUME] {n}/{total} {wid}"); continue
        q0=_ms(d,a)-int(self.plan["calendar"]["query_padding_before_seconds"])*1000; q1=_ms(d,b)+int(self.plan["calendar"]["query_padding_after_seconds"])*1000
        if q1>=protected: raise CaptureContractError("query reaches protected forward")
        ticks={}; prov=[]
        for t in self.plan["targets"]:
          ticks[t["symbol"]]={}
          for side in ("BID","ASK"):
            vals,p=self._side(aid,t,side,q0,q1); ticks[t["symbol"]][side]=vals; prov.append(p)
        rows=self._eval(d,a,b,ticks,q0//1000,q1//1000); out=self._wpath(wid); self._write(out,rows)
        pp=self.out/"provenance"/f"{wid}.json"; atomic_write_json(pp,{"window_id":wid,"query_from_ms":q0,"query_to_ms":q1,"side_capture":prov,"event_rows":len(rows),"raw_ticks_transferred":False,"fill_authority":False,"orders":False})
        self.resume["completed_windows"][wid]={"sha256":sha256_file(out),"event_rows":len(rows),"provenance_sha256":sha256_file(pp)}; atomic_write_json(self.resume_path,self.resume)
        self.progress(f"[WINDOW] {n}/{total} {wid} | events={len(rows)} | historical_requests={self.hist_requests}")

  def _final(self):
    self.progress("[3/4] Finalizing sanitized evidence; raw ticks excluded"); self.out.mkdir(parents=True,exist_ok=True)
    files=[{"path":p.relative_to(self.out).as_posix(),"bytes":p.stat().st_size,"sha256":sha256_file(p)} for p in sorted(x for x in self.out.rglob("*") if x.is_file()) if p.name not in {"MANIFEST.json","CHECKSUMS.sha256"}]
    atomic_write_json(self.out/"MANIFEST.json",{"schema":"mxm.research-core-v3.fx-cross-pair-quote-lead-lag-evidence.v2","tool_version":TOOL_VERSION,"plan_binding_sha256":self.plan["binding_sha256"],"primary_design_sha256":self.design["canonical_sha256"],"preoutcome_audit_sha256":self.audit["canonical_sha256"],"diagnostic_freeze_sha256":self.diag["canonical_sha256"],"primary_frozen_test_count":72,"primary_design_changed":False,"diagnostic_path_horizon_seconds":900,"historical_requests":self.hist_requests,"completed_core_windows":len(self.resume["completed_windows"]),"expected_core_windows":78,"account":self.account_evidence,"symbols":self.symbol_evidence,"files":files,"raw_tick_values_in_transfer":False,"fill_authority":False,"orders":False,"automatic_additional_acquisition":False,"protected_forward_opened":False,"candidate_freeze_from_capture":False,"diagnostic_fields_may_enter_primary_maxT":False})
    chk=[]
    for p in sorted(x for x in self.out.rglob("*") if x.is_file() and x.name!="CHECKSUMS.sha256"): chk.append(f"{sha256_file(p)}  {p.relative_to(self.out).as_posix()}")
    (self.out/"CHECKSUMS.sha256").write_text("\n".join(chk)+"\n",encoding="utf-8"); self.transfer.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(self.transfer,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
      for p in sorted(x for x in self.out.rglob("*") if x.is_file()):
        i=zipfile.ZipInfo(p.relative_to(self.out).as_posix(),date_time=(1980,1,1,0,0,0)); i.compress_type=zipfile.ZIP_DEFLATED; i.external_attr=0o644<<16; z.writestr(i,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    self.progress("[4/4] Evidence bundle complete"); return self.transfer

  def run(self):
    aid=self._auth(); self._capture(aid); return self._final()
