from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from research_core_v4 import response_evaluator_v3 as ev
    from research_core_v4.frozen_v2_semantics import canonical_json_bytes
except ModuleNotFoundError:
    import response_evaluator_v3 as ev
    from frozen_v2_semantics import canonical_json_bytes

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_REL = "research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_EXECUTION_AUTHORITY_V3.json"
STATE_REL = "research_core_v4/state/V4_STATE.json"
DESIGN_REL = "research_core_v4/state/FIRST_REAL_MARKET_DESIGN_V2.json"
MANIFEST_REL = "research_core_v3/state/PRIMARY_145_INPUT_MANIFEST_V1.json"
SUPPORT_REL = "research_core_v4/state/V4_REAL_SUPPORT_SKELETON_AUDIT_V1.json"
EVALUATOR_REL = "research_core_v4/response_evaluator_v3.py"
LEGACY_EVALUATOR_V2_REL = "research_core_v4/response_evaluator_v2.py"
SEMANTICS_REL = "research_core_v4/frozen_v2_semantics.py"
CALIBRATION_REL = "research_core_v4/state/EXACT_SUPPORT_GEOMETRY_CALIBRATION_RESULT_V2.json"
CONFIRMATION_LAW_REL = "research_core_v4/state/CONFIRMATION_PASS_LAW_V1.json"
CONFIRMATION_PROVENANCE_REL = "research_core_v4/state/CONFIRMATION_PROVENANCE_CERTIFICATE_V1.json"
DIAGNOSTICS_REL = "research_core_v4/state/NONSELECTION_DIAGNOSTIC_IMPLEMENTATION_V1.json"
ALIGNMENT_REL = "research_core_v4/state/PRODUCTION_CALIBRATION_SEMANTICS_ALIGNMENT_V1.json"
IMPLEMENTATION_CONTRACT_REL = "research_core_v4/state/RESPONSE_EVALUATOR_IMPLEMENTATION_CONTRACT_V2.json"
INDEPENDENT_AUDIT_REL = "research_core_v4/state/FRESH_INDEPENDENT_PREOUTCOME_AUDIT_V2.json"
VALIDATION_POLICY_REL = "research_core_v4/state/FINAL_PREOUTCOME_VALIDATION_POLICY_V2.json"
AUTHORITY_V2_SUPERSESSION_REL = "research_core_v4/state/FIRST_V4_DEVELOPMENT_RESPONSE_EXECUTION_AUTHORITY_V2_SUPERSESSION_V1.json"
RESPONSE_OPENING_STARTED = False

@dataclass(frozen=True)
class PrevalidatedBundle:
    authority: dict
    state: dict
    design: dict
    manifest: dict
    support: dict
    events: tuple
    bars_by_symbol: dict
    source_hashes: dict[str,str]
    provenance: dict


def sha256_file(path: str | Path) -> str:
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def state_binding_payload(state: dict) -> dict:
    fw=state["first_wave"];g=state["governance"]
    return {
        "schema":state["schema"],
        "status":state["status"],
        "design":fw["design"],
        "development_response_execution_authority":fw["development_response_execution_authority"],
        "execution_authority_v1_status":fw["execution_authority_v1_status"],
        "execution_authority_v2_status":fw["execution_authority_v2_status"],
        "legacy_evaluator_v2_status":fw["legacy_evaluator_v2_status"],
        "response_evaluator_implementation_contract":fw["response_evaluator_implementation_contract"],
        "final_preoutcome_scientific_audit":state["final_preoutcome_scientific_audit"],
        "final_preoutcome_validation_policy":state["final_preoutcome_validation_policy"],
        "evaluator_execution_authorized":fw["evaluator_execution_authorized"],
        "confirmation_execution_authorized":fw["confirmation_execution_authorized"],
        "development_outcomes_opened":fw["development_outcomes_opened"],
        "confirmation_outcomes_opened":fw["confirmation_outcomes_opened"],
        "new_market_acquisition_started":fw["new_market_acquisition_started"],
        "broker_acquisition_authorized":g["broker_acquisition_authorized"],
        "quote_revision_v2_execution_authorized":g["quote_revision_v2_execution_authorized"],
        "protected_forward_opened":g["protected_forward_opened"],
        "candidate_promotion_authorized":g["candidate_promotion_authorized"],
        "candidate_frozen_count":g["candidate_frozen_count"],
        "live_trading_started":g["live_trading_started"],
    }


def state_binding_sha256(state: dict) -> str:
    return sha256_bytes(canonical_json_bytes(state_binding_payload(state)))


def _must_equal(name: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise PermissionError(f"PRE_RESPONSE_GUARD_FAIL {name}: {actual!r} != {expected!r}")


def verify_bound_file(name: str, path: str | Path, expected_sha256: str) -> str:
    actual=sha256_file(path)
    _must_equal(name,actual,expected_sha256)
    return actual


def verify_series_file(path: str | Path, item: dict) -> tuple[list[ev.M5Bar],str]:
    digest=verify_bound_file(f"series_sha256:{item['symbol']}",path,item["series_sha256"])
    bars=ev.read_m5_csv(path)
    _must_equal(f"row_count:{item['symbol']}",len(bars),int(item["row_count"]))
    _must_equal(f"first_timestamp:{item['symbol']}",bars[0].time.isoformat().replace("+00:00","Z"),item["first_timestamp_utc"])
    _must_equal(f"last_timestamp:{item['symbol']}",bars[-1].time.isoformat().replace("+00:00","Z"),item["last_timestamp_utc"])
    return bars,digest


def verify_rebuilt_skeleton(events, expected_sha256: str, expected_rows: int) -> str:
    digest=ev.skeleton_sha256(events)
    _must_equal("rebuilt_skeleton_sha256",digest,expected_sha256)
    _must_equal("rebuilt_skeleton_row_count",len(events),int(expected_rows))
    return digest


def verify_static_bindings(authority: dict, state: dict, design: dict, manifest: dict, support: dict) -> None:
    ev.require_real_response_authority(authority)
    b=authority["bindings"]
    _must_equal("canonical_state_status",state["status"],b["canonical_state_status"])
    _must_equal("canonical_state_binding_sha256",state_binding_sha256(state),b["canonical_state_binding_sha256"])
    _must_equal("design_sha256",sha256_file(ROOT/DESIGN_REL),b["canonical_design_content_sha256"])
    _must_equal("evaluator_sha256",sha256_file(ROOT/EVALUATOR_REL),b["evaluator_content_sha256"])
    _must_equal("legacy_evaluator_v2_sha256",sha256_file(ROOT/LEGACY_EVALUATOR_V2_REL),b["legacy_evaluator_v2_content_sha256"])
    _must_equal("semantics_sha256",sha256_file(ROOT/SEMANTICS_REL),b["shared_semantics_content_sha256"])
    _must_equal("runner_sha256",sha256_file(Path(__file__).resolve()),b["execution_runner_content_sha256"])
    _must_equal("manifest_sha256",sha256_file(ROOT/MANIFEST_REL),b["canonical_primary_manifest_content_sha256"])
    _must_equal("support_audit_sha256",sha256_file(ROOT/SUPPORT_REL),b["support_audit_content_sha256"])
    _must_equal("calibration_sha256",sha256_file(ROOT/CALIBRATION_REL),b["exact_geometry_calibration_content_sha256"])
    _must_equal("confirmation_law_sha256",sha256_file(ROOT/CONFIRMATION_LAW_REL),b["confirmation_pass_law_content_sha256"])
    _must_equal("confirmation_provenance_sha256",sha256_file(ROOT/CONFIRMATION_PROVENANCE_REL),b["confirmation_provenance_content_sha256"])
    _must_equal("diagnostics_sha256",sha256_file(ROOT/DIAGNOSTICS_REL),b["nonselection_diagnostic_implementation_content_sha256"])
    _must_equal("alignment_sha256",sha256_file(ROOT/ALIGNMENT_REL),b["production_calibration_alignment_content_sha256"])
    _must_equal("implementation_contract_sha256",sha256_file(ROOT/IMPLEMENTATION_CONTRACT_REL),b["response_evaluator_implementation_contract_content_sha256"])
    _must_equal("independent_audit_sha256",sha256_file(ROOT/INDEPENDENT_AUDIT_REL),b["fresh_independent_preoutcome_audit_content_sha256"])
    _must_equal("validation_policy_sha256",sha256_file(ROOT/VALIDATION_POLICY_REL),b["final_preoutcome_validation_policy_content_sha256"])
    _must_equal("authority_v2_supersession_sha256",sha256_file(ROOT/AUTHORITY_V2_SUPERSESSION_REL),b["authority_v2_supersession_content_sha256"])
    _must_equal("support_skeleton_sha256",support["skeleton"]["canonical_sha256"],b["support_skeleton_sha256"])
    _must_equal("support_skeleton_row_count",support["skeleton"]["row_count"],b["support_skeleton_row_count"])

    _must_equal("state_current_authority_pointer",state["first_wave"]["development_response_execution_authority"],AUTHORITY_REL)
    _must_equal("state_authority_v1_status",state["first_wave"]["execution_authority_v1_status"],"SUPERSEDED_BEFORE_ANY_REAL_V4_RESPONSE")
    _must_equal("state_authority_v2_status",state["first_wave"]["execution_authority_v2_status"],"SUPERSEDED_BEFORE_ANY_REAL_V4_RESPONSE")
    _must_equal("state_legacy_evaluator_v2_status",state["first_wave"]["legacy_evaluator_v2_status"],"SUPERSEDED_EXECUTION_DISABLED")
    _must_equal("state_evaluator_pointer",state["first_wave"]["development_response_evaluator"],EVALUATOR_REL)
    _must_equal("state_runner_pointer",state["first_wave"]["development_execution_runner"],"research_core_v4/development_execution_runner_v1.py")
    _must_equal("state_calibration_pointer",state["first_wave"]["exact_geometry_calibration"],CALIBRATION_REL)
    _must_equal("state_diagnostics_pointer",state["first_wave"]["nonselection_diagnostic_implementation"],DIAGNOSTICS_REL)
    _must_equal("state_implementation_contract_pointer",state["first_wave"]["response_evaluator_implementation_contract"],IMPLEMENTATION_CONTRACT_REL)
    _must_equal("state_independent_audit_pointer",state["final_preoutcome_scientific_audit"],INDEPENDENT_AUDIT_REL)
    _must_equal("state_validation_policy_pointer",state["final_preoutcome_validation_policy"],VALIDATION_POLICY_REL)
    scope=authority["development_scope"]
    _must_equal("contexts",[x["id"] for x in design["structural_contexts"]],scope["contexts"])
    _must_equal("volatility_states",list(ev.VOL_STATES),scope["volatility_states"])
    _must_equal("horizons",list(ev.HORIZONS),scope["response_horizons_m5"])
    _must_equal("permutations",ev.DEFAULT_PERMUTATIONS,scope["permutations"])
    _must_equal("seed",ev.DEFAULT_SEED,scope["seed"])
    _must_equal("development_interval",design["development_interval_utc"],scope["development_interval_utc"])

    if state["first_wave"]["confirmation_execution_authorized"] is not False:
        raise PermissionError("PRE_RESPONSE_GUARD_FAIL confirmation execution")
    if state["governance"]["broker_acquisition_authorized"] is not False:
        raise PermissionError("PRE_RESPONSE_GUARD_FAIL broker acquisition")
    if state["governance"]["quote_revision_v2_execution_authorized"] is not False:
        raise PermissionError("PRE_RESPONSE_GUARD_FAIL quote revision V2")
    if state["governance"]["protected_forward_opened"] is not False:
        raise PermissionError("PRE_RESPONSE_GUARD_FAIL protected forward")
    if state["governance"]["candidate_promotion_authorized"] is not False:
        raise PermissionError("PRE_RESPONSE_GUARD_FAIL candidate promotion")
    if state["governance"]["live_trading_started"] is not False:
        raise PermissionError("PRE_RESPONSE_GUARD_FAIL live trading")
    if state["first_wave"]["development_outcomes_opened"] is not False:
        raise PermissionError("PRE_RESPONSE_GUARD_FAIL development already opened")


def _manifest_binding_map(manifest: dict) -> dict[int,dict]:
    return {int(x["symbol_id"]):x for x in manifest["primary_series"]}


def pre_response_guards(raw_root: str | Path) -> PrevalidatedBundle:
    authority=load_json(ROOT/AUTHORITY_REL)
    state=load_json(ROOT/STATE_REL)
    design=load_json(ROOT/DESIGN_REL)
    manifest=load_json(ROOT/MANIFEST_REL)
    support=load_json(ROOT/SUPPORT_REL)
    verify_static_bindings(authority,state,design,manifest,support)

    expected=authority["bindings"]["development_series"]
    manifest_by_id=_manifest_binding_map(manifest)
    design_pairs=[(c["id"],sym,int(sid)) for c in design["structural_contexts"] for sym,sid in c["development_symbols"]]
    expected_ids={int(x["symbol_id"]) for x in expected}
    _must_equal("development_identity_count",len(design_pairs),18)
    _must_equal("development_identity_set",{sid for _,_,sid in design_pairs},expected_ids)

    raw_root=Path(raw_root)
    bars_by_symbol={}
    source_hashes={}
    all_events=[]
    for item in expected:
        sid=int(item["symbol_id"]);sym=item["symbol"];p=raw_root/f"{sid}_M5.csv"
        if not p.exists():
            raise FileNotFoundError(f"PRE_RESPONSE_GUARD_FAIL missing frozen input {p}")
        m=manifest_by_id.get(sid)
        if m is None:
            raise PermissionError(f"PRE_RESPONSE_GUARD_FAIL manifest missing {sid}")
        for key in ("symbol","row_count","series_sha256","first_timestamp_utc","last_timestamp_utc","source_archive_sha256"):
            _must_equal(f"manifest:{sym}:{key}",m[key],item[key])
        bars,digest=verify_series_file(p,item)
        bars_by_symbol[sym]=bars
        source_hashes[sym]=digest

    start=ev.parse_utc(design["development_interval_utc"][0]);end=ev.parse_utc(design["development_interval_utc"][1])
    for ctx,sym,sid in design_pairs:
        bars=[b for b in bars_by_symbol[sym] if start <= b.time <= end]
        all_events.extend(ev.build_signal_support(bars,ctx,sym,sid))

    skeleton_sha=verify_rebuilt_skeleton(
        all_events,
        authority["bindings"]["support_skeleton_sha256"],
        authority["bindings"]["support_skeleton_row_count"],
    )

    context_counts={}
    for ctx in authority["development_scope"]["contexts"]:
        ce=[e for e in all_events if e.context==ctx]
        context_counts[ctx]={
            "events":len(ce),
            "full":sum(e.arm=="FULL" for e in ce),
            "baseline":sum(e.arm=="BASELINE" for e in ce),
        }
        frozen=support["context_event_counts"][ctx]
        for k in ("events","full","baseline"):
            _must_equal(f"context_support:{ctx}:{k}",context_counts[ctx][k],frozen[k])

    provenance={
        "authority_sha256":sha256_file(ROOT/AUTHORITY_REL),
        "canonical_state_file_sha256":sha256_file(ROOT/STATE_REL),
        "canonical_state_binding_sha256":state_binding_sha256(state),
        "canonical_design_sha256":sha256_file(ROOT/DESIGN_REL),
        "evaluator_sha256":sha256_file(ROOT/EVALUATOR_REL),
        "legacy_evaluator_v2_sha256":sha256_file(ROOT/LEGACY_EVALUATOR_V2_REL),
        "execution_runner_sha256":sha256_file(Path(__file__).resolve()),
        "shared_semantics_sha256":sha256_file(ROOT/SEMANTICS_REL),
        "primary_manifest_sha256":sha256_file(ROOT/MANIFEST_REL),
        "support_audit_sha256":sha256_file(ROOT/SUPPORT_REL),
        "exact_geometry_calibration_sha256":sha256_file(ROOT/CALIBRATION_REL),
        "confirmation_pass_law_sha256":sha256_file(ROOT/CONFIRMATION_LAW_REL),
        "confirmation_provenance_sha256":sha256_file(ROOT/CONFIRMATION_PROVENANCE_REL),
        "nonselection_diagnostic_implementation_sha256":sha256_file(ROOT/DIAGNOSTICS_REL),
        "production_calibration_alignment_sha256":sha256_file(ROOT/ALIGNMENT_REL),
        "response_evaluator_implementation_contract_sha256":sha256_file(ROOT/IMPLEMENTATION_CONTRACT_REL),
        "fresh_independent_preoutcome_audit_sha256":sha256_file(ROOT/INDEPENDENT_AUDIT_REL),
        "final_preoutcome_validation_policy_sha256":sha256_file(ROOT/VALIDATION_POLICY_REL),
        "rebuilt_support_skeleton_sha256":skeleton_sha,
        "rebuilt_support_skeleton_row_count":len(all_events),
        "source_series_sha256":source_hashes,
        "development_series_binding":authority["bindings"]["development_series"],
        "source_archives":{
            "original_archive_sha256":authority["bindings"]["original_archive_sha256"],
            "delta_archive_sha256":authority["bindings"]["delta_archive_sha256"],
        },
        "context_support_counts":context_counts,
        "development_scope":authority["development_scope"],
        "seed":ev.DEFAULT_SEED,
        "permutations":ev.DEFAULT_PERMUTATIONS,
    }
    return PrevalidatedBundle(authority,state,design,manifest,support,tuple(all_events),bars_by_symbol,source_hashes,provenance)


def execute_once(bundle: PrevalidatedBundle, output: str | Path) -> str:
    global RESPONSE_OPENING_STARTED
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    lock=output.with_suffix(output.suffix+".opening.lock")
    if RESPONSE_OPENING_STARTED:
        raise PermissionError("response opening already started in this process")
    if output.exists():
        raise PermissionError("authorized development result already exists; refusing duplicate execution")
    try:
        fd=os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError as exc:
        raise PermissionError("durable response-opening lock already exists; refusing duplicate execution") from exc
    with os.fdopen(fd,"w",encoding="utf-8") as f:
        f.write(sha256_file(ROOT/AUTHORITY_REL)+"\n");f.flush();os.fsync(f.fileno())
    RESPONSE_OPENING_STARTED=True
    capability=ev._runner_execution_capability()
    result=ev._evaluate_prevalidated_development_core(
        authority=bundle.authority,
        design=bundle.design,
        events=bundle.events,
        bars_by_symbol=bundle.bars_by_symbol,
        source_hashes=bundle.source_hashes,
        permutations=ev.DEFAULT_PERMUTATIONS,
        seed=ev.DEFAULT_SEED,
        _execution_capability=capability,
    )
    result["execution_provenance"]=bundle.provenance
    result["authority_status_at_open"]=bundle.authority["status"]
    result["canonical_state_status_at_open"]=bundle.state["status"]
    result["confirmation_execution_authorized"]=False
    result["broker_acquisition_authorized"]=False
    result["candidate_promotion_authorized"]=False
    raw=canonical_json_bytes(result)
    digest=sha256_bytes(raw)
    result["raw_result_sha256_without_self_field"]=digest
    raw=canonical_json_bytes(result)
    final_digest=sha256_bytes(raw)

    tmp=output.with_suffix(output.suffix+".tmp")
    with tmp.open("wb") as f:
        f.write(raw);f.flush();os.fsync(f.fileno())
    os.replace(tmp,output)
    print(f"RESULT_WRITTEN {final_digest}")
    return final_digest


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--raw-root",type=Path)
    ap.add_argument("--output",type=Path,default=Path("V4_FIRST_DEVELOPMENT_RESPONSE_RESULT_V1.json"))
    ap.add_argument("--execute-authorized-development",action="store_true")
    ap.add_argument("--self-test-summary",action="store_true")
    args=ap.parse_args()
    if args.self_test_summary:
        print(json.dumps({
            "runner":"development_execution_runner_v1",
            "default":"DENIED",
            "authority_path":AUTHORITY_REL,
            "design_path":DESIGN_REL,
            "seed":ev.DEFAULT_SEED,
            "permutations":ev.DEFAULT_PERMUTATIONS,
            "horizons":list(ev.HORIZONS),
            "volatility_states":list(ev.VOL_STATES),
        },sort_keys=True))
        return
    if not args.execute_authorized_development:
        raise SystemExit("DENIED: explicit --execute-authorized-development is required")
    if args.raw_root is None:
        raise SystemExit("DENIED: --raw-root is required")
    bundle=pre_response_guards(args.raw_root)
    execute_once(bundle,args.output)


if __name__=="__main__":
    main()
