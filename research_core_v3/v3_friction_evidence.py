"""Fail-closed verifier for the V3 maxT14 historical BID/ASK evidence bundle."""
from __future__ import annotations

import csv, gzip, hashlib, io, json, math, zipfile
from pathlib import Path
from typing import Any

PLAN_REL = Path("research_core_v3/state/MAXT14_AUTHENTIC_FRICTION_ACQUISITION_PLAN_V1.json")
BUNDLE_SCHEMA = "mxm.research-core-v3.maxt14-friction-evidence-bundle.v1"
ASSESSMENT_SCHEMA = "mxm.research-core-v3.maxt14-friction-evidence-assessment.v1"
TWO = "CAUSAL_TWO_SIDED_AVAILABLE"
AVAIL = {TWO, "MISSING_BID", "MISSING_ASK", "MISSING_BOTH_SIDES"}

class FrictionEvidenceError(ValueError):
    pass

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _canonical(x: Any) -> bytes:
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

def _bound(doc: dict[str, Any]) -> None:
    claimed = str(doc.get("binding_sha256") or "")
    raw = dict(doc); raw.pop("binding_sha256", None)
    if len(claimed) != 64 or _sha(_canonical(raw)) != claimed:
        raise FrictionEvidenceError("binding_sha256 mismatch")

def _num(value: str, label: str) -> float:
    try: x = float(value)
    except (TypeError, ValueError) as exc: raise FrictionEvidenceError(f"invalid {label}") from exc
    if not math.isfinite(x): raise FrictionEvidenceError(f"non-finite {label}")
    return x

def _int(value: str, label: str) -> int:
    try: return int(value)
    except (TypeError, ValueError) as exc: raise FrictionEvidenceError(f"invalid {label}") from exc

def _dist(values: list[float]) -> dict[str, Any]:
    if not values: return {"n":0,"mean":None,"median":None,"p90":None,"p95":None,"p99":None,"max":None}
    values.sort(); n=len(values)
    q=lambda p: values[max(0,min(n-1,math.ceil(p*n)-1))]
    return {"n":n,"mean":sum(values)/n,"median":q(.5),"p90":q(.9),"p95":q(.95),"p99":q(.99),"max":values[-1]}

def _archive(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as zf:
        names=zf.namelist()
        if len(names)!=len(set(names)) or zf.testzip() is not None: raise FrictionEvidenceError("ZIP integrity failure")
        files={n:zf.read(n) for n in names if not n.endswith("/")}
    if "CHECKSUMS.sha256" not in files or "evidence/provenance_manifest.json" not in files:
        raise FrictionEvidenceError("provenance files missing")
    checks={}
    for line in files["CHECKSUMS.sha256"].decode().splitlines():
        if not line: continue
        try: digest,name=line.split("  ",1)
        except ValueError as exc: raise FrictionEvidenceError("malformed checksum manifest") from exc
        if len(digest)!=64 or not name or name in checks: raise FrictionEvidenceError("invalid checksum entry")
        checks[name]=digest
    if set(checks)!=(set(files)-{"CHECKSUMS.sha256"}): raise FrictionEvidenceError("checksum coverage mismatch")
    for name,digest in checks.items():
        if _sha(files[name])!=digest: raise FrictionEvidenceError(f"checksum mismatch: {name}")
    return files

def _csv_summary(blob: bytes, target: dict[str, Any], delays: list[int], age_limit: int) -> dict[str, Any]:
    symbol=str(target["symbol"]); sid=int(target["symbol_id"]); expected=int(target["windows"]); region=str(target["region_sha256"])
    try: reader=csv.DictReader(io.StringIO(gzip.decompress(blob).decode()))
    except Exception as exc: raise FrictionEvidenceError(f"{symbol}: invalid derived CSV") from exc
    required={"symbol","symbol_id","exact_window_index","window_start_ms","boundary_ms","window_end_ms","region_sha256"}
    for d in delays:
        p=f"d{d}s"; required|={f"{p}_bid",f"{p}_ask",f"{p}_spread",f"{p}_bid_timestamp_ms",f"{p}_ask_timestamp_ms",f"{p}_bid_age_ms",f"{p}_ask_age_ms",f"{p}_availability"}
    if not reader.fieldnames or not required.issubset(reader.fieldnames): raise FrictionEvidenceError(f"{symbol}: schema mismatch")
    stats={d:{"two_sided":0,"fresh_two_sided":0,"stale_two_sided":0,"missing_bid":0,"missing_ask":0,"missing_both":0,"negative_spread":0,"bps":[]} for d in delays}
    seen=set(); rows=0
    for row in reader:
        idx=_int(row["exact_window_index"],f"{symbol}.index")
        if idx in seen: raise FrictionEvidenceError(f"{symbol}: duplicate window index")
        seen.add(idx)
        if row["symbol"]!=symbol or _int(row["symbol_id"],f"{symbol}.id")!=sid or row["region_sha256"]!=region: raise FrictionEvidenceError(f"{symbol}: identity binding mismatch")
        start=_int(row["window_start_ms"],"start"); boundary=_int(row["boundary_ms"],"boundary"); end=_int(row["window_end_ms"],"end")
        if boundary-start!=2000 or end-boundary!=30000: raise FrictionEvidenceError(f"{symbol}: window geometry mismatch")
        for d in delays:
            p=f"d{d}s"; state=row[f"{p}_availability"]
            if state not in AVAIL: raise FrictionEvidenceError(f"{symbol}: invalid availability")
            s=stats[d]
            if state!=TWO:
                s[{"MISSING_BID":"missing_bid","MISSING_ASK":"missing_ask","MISSING_BOTH_SIDES":"missing_both"}[state]]+=1
                if row[f"{p}_spread"]: raise FrictionEvidenceError(f"{symbol}: spread with missing side")
                continue
            bid=_num(row[f"{p}_bid"],"bid"); ask=_num(row[f"{p}_ask"],"ask"); spread=_num(row[f"{p}_spread"],"spread")
            bt=_int(row[f"{p}_bid_timestamp_ms"],"bid timestamp"); at=_int(row[f"{p}_ask_timestamp_ms"],"ask timestamp")
            ba=_int(row[f"{p}_bid_age_ms"],"bid age"); aa=_int(row[f"{p}_ask_age_ms"],"ask age"); checkpoint=boundary+d*1000
            if ba<0 or aa<0 or checkpoint-bt!=ba or checkpoint-at!=aa: raise FrictionEvidenceError(f"{symbol}: noncausal quote age")
            if abs((ask-bid)-spread)>max(1e-12,abs(spread)*1e-9): raise FrictionEvidenceError(f"{symbol}: spread arithmetic mismatch")
            s["two_sided"]+=1; stale=max(ba,aa)>age_limit
            s["stale_two_sided" if stale else "fresh_two_sided"]+=1
            if spread<0: s["negative_spread"]+=1
            elif not stale:
                mid=(bid+ask)/2
                if mid<=0: raise FrictionEvidenceError(f"{symbol}: non-positive midpoint")
                s["bps"].append(spread/mid*10000)
        rows+=1
    if rows!=expected or seen!=set(range(expected)): raise FrictionEvidenceError(f"{symbol}: exact-window coverage mismatch")
    out={}
    for d,s in stats.items():
        out[f"d{d}s"]={k:v for k,v in s.items() if k!="bps"}
        out[f"d{d}s"]["fresh_two_sided_ratio"]=s["fresh_two_sided"]/rows if rows else 0
        out[f"d{d}s"]["spread_bps_fresh_nonnegative"]=_dist(s["bps"])
    return {"rows":rows,"delays":out,"missing_two_sided_at_boundary":rows-stats[0]["two_sided"],"two_sided_but_older_than_2s_at_boundary":stats[0]["stale_two_sided"],"negative_spread_states_across_delays":sum(s["negative_spread"] for s in stats.values())}

def assess_bundle(repo_root: Path, bundle_path: Path, *, plan_path: Path|None=None) -> dict[str, Any]:
    plan=json.loads((Path(plan_path) if plan_path else Path(repo_root)/PLAN_REL).read_text()); _bound(plan)
    if plan.get("status")!="FROZEN_READ_ONLY_AUTHENTIC_QUOTE_ACQUISITION_PLAN": raise FrictionEvidenceError("plan not frozen")
    targets=plan["targets"]; expected=int(plan["selection"]["selected_exact_quote_windows"])
    if len(targets)!=int(plan["selection"]["selected_regions"]) or sum(int(t["windows"]) for t in targets)!=expected: raise FrictionEvidenceError("plan geometry mismatch")
    files=_archive(Path(bundle_path)); manifest=json.loads(files["evidence/provenance_manifest.json"]); _bound(manifest)
    if manifest.get("schema")!=BUNDLE_SCHEMA or manifest.get("plan_binding_sha256")!=plan["binding_sha256"]: raise FrictionEvidenceError("bundle/plan mismatch")
    if manifest.get("source_corrected_region_assessment_sha256")!=plan["authority"]["corrected_region_assessment_sha256"] or manifest.get("source_corrected_friction_scope_plan_sha256")!=plan["authority"]["corrected_friction_scope_plan_sha256"]: raise FrictionEvidenceError("source binding mismatch")
    if manifest.get("account_fingerprint_sha256")!=plan["broker_identity"]["accepted_account_fingerprint_sha256"]: raise FrictionEvidenceError("account fingerprint mismatch")
    forbidden=("protected_forward_opened","candidate_outcomes_opened","orders","account_mutation","fill_authority","economic_certification","candidate_freeze_authority","raw_ticks_embedded_in_transfer_bundle")
    if any(bool(manifest.get(k)) for k in forbidden): raise FrictionEvidenceError("forbidden authority/state in bundle")
    geometry=manifest.get("geometry",{})
    if int(geometry.get("symbols",-1))!=len(targets) or int(geometry.get("exact_windows",-1))!=expected: raise FrictionEvidenceError("bundle geometry mismatch")
    dm=manifest.get("derived_exact_window_evidence",{})
    if set(dm)!={str(t["symbol"]) for t in targets}: raise FrictionEvidenceError("derived symbol set mismatch")
    delays=[int(x) for x in plan["acquisition"]["delay_sensitivity_seconds"]]; age=int(plan["acquisition"]["quote_age_limit_seconds"])*1000
    symbols={}; total=0
    for t in targets:
        symbol=str(t["symbol"]); meta=dm[symbol]; path=str(meta.get("path") or "")
        if path not in files or _sha(files[path])!=meta.get("sha256") or int(meta.get("rows",-1))!=int(t["windows"]): raise FrictionEvidenceError(f"{symbol}: manifest payload mismatch")
        summary=_csv_summary(files[path],t,delays,age)
        for key in ("missing_two_sided_at_boundary","two_sided_but_older_than_2s_at_boundary","negative_spread_states_across_delays"):
            if int(meta.get(key,-1))!=int(summary[key]): raise FrictionEvidenceError(f"{symbol}: summary mismatch")
        symbols[symbol]={"symbol_id":int(t["symbol_id"]),"region_sha256":t["region_sha256"],"minimum_gross_mean_response_bps":float(t["minimum_mean_response_bps"]),**summary}; total+=summary["rows"]
    if total!=expected: raise FrictionEvidenceError("validated total mismatch")
    return {"schema":ASSESSMENT_SCHEMA,"status":"AUTHENTIC_HISTORICAL_BID_ASK_EVIDENCE_ACCEPTED_OTHER_COST_COMPONENTS_UNRESOLVED","bundle_sha256":_sha(Path(bundle_path).read_bytes()),"bundle_manifest_binding_sha256":manifest["binding_sha256"],"plan_binding_sha256":plan["binding_sha256"],"source_corrected_surface_sha256":plan["authority"]["corrected_surface_sha256"],"source_corrected_region_assessment_sha256":plan["authority"]["corrected_region_assessment_sha256"],"account_fingerprint_sha256":manifest["account_fingerprint_sha256"],"historical_bid_ask_component_accepted":True,"historical_bid_ask_symbols":len(symbols),"historical_bid_ask_exact_windows":total,"protected_forward_opened":False,"candidate_outcomes_opened":False,"candidate_frozen":False,"net_certification":False,"confirmation_ready":False,"gross_survivor_regions_total":int(plan["selection"]["gross_robust_regions_total"]),"quote_resolved_priority_regions":len(symbols),"other_gross_regions_remaining_cost_unresolved":int(plan["selection"]["other_gross_regions_remaining_COST_UNRESOLVED"]),"remaining_required_components":list(plan["freeze_gate"]["remaining_required_components"]),"interpretation":"Authenticated historical quote evidence only; spread distributions are not fills or net-edge certification.","quantile_method":"nearest_rank","symbols":symbols}

def write_assessment(assessment: dict[str, Any], output_path: Path) -> None:
    Path(output_path).write_text(json.dumps(assessment,sort_keys=True,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
