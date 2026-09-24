"""One-button Pydroid launcher for the frozen independent six-panel outer capture."""
from __future__ import annotations
import inspect, json
from pathlib import Path

from m6.ctrader_capture import CaptureContractError, FORBIDDEN_MUTATION_PROTO_REQUESTS, require_read_only_request, redact_text
from m6.pydroid_oauth import ACCOUNT_SELECTION_PATH, choose_live_account_locally, ensure_v2_authorization, load_saved_account_id
from research_v3.session_gap_six_panel_outer_capture import (
    BASE_PROTOCOL_REL, PLAN_REL, SixPanelIndependentOuterCaptureRunner, validate_outer_plan,
)

ROOT=Path(__file__).resolve().parents[1]
ALLOWED=frozenset({
    "ProtoOAApplicationAuthReq","ProtoOAGetAccountListByAccessTokenReq","ProtoOAAccountAuthReq","ProtoOATraderReq",
    "ProtoOAAssetListReq","ProtoOASymbolsListReq","ProtoOASymbolByIdReq","ProtoOAGetTrendbarsReq",
    "ProtoOAGetTickDataReq","ProtoOASymbolsForConversionReq",
})

def load_plan():
    plan=json.loads((ROOT/PLAN_REL).read_text(encoding="utf-8")); validate_outer_plan(plan); return plan

def load_protocol():
    return json.loads((ROOT/BASE_PROTOCOL_REL).read_text(encoding="utf-8"))

def local_preflight():
    plan=load_plan()
    for name in ALLOWED: require_read_only_request(name)
    for name in FORBIDDEN_MUTATION_PROTO_REQUESTS:
        try: require_read_only_request(name)
        except CaptureContractError: pass
        else: raise CaptureContractError(f"mutation unexpectedly allowed: {name}")
    source=inspect.getsource(__import__("research_v3.session_gap_six_panel_outer_capture",fromlist=["*"]))
    for forbidden in ("ProtoOANewOrderReq","ProtoOACancelOrderReq","ProtoOAClosePositionReq","ProtoOAAmendOrderReq"):
        if forbidden in source: raise CaptureContractError(f"forbidden trading token: {forbidden}")
    return {
        "plan_sha256":plan["plan_sha256"],"symbols":len(plan["symbols"]),"resolution":plan["resolution"],
        "outer_interval":plan["outer_interval"],"wave01_interval":plan["source_wave01_interval"],
        "disjoint":plan["outer_interval"]["end_utc"]<plan["source_wave01_interval"]["start_utc"],
        "friction_sample_dates":plan["friction_authority"]["sample_dates"],
        "network_connection_attempted":False,"credentials_used":False,"orders_permitted":False,
        "account_mutation_permitted":False,"protected_evidence_opened":False,
        "outer_outcome_opened":False,"economic_outcomes_opened":False,"v2_attempts_consumed":0,
    }

def main():
    print("MXM SESSION-GAP SIX-PANEL OUTER | M5 16W + historical friction | READ ONLY | outer outcome=NO")
    try:
        print("[PREFLIGHT PASS]",local_preflight())
        app,token,mode=ensure_v2_authorization(); print("[OAUTH]",mode)
        config={"ctid_trader_account_id":load_saved_account_id(),"account_selection_path":str(ACCOUNT_SELECTION_PATH),"account_selector":choose_live_account_locally}
        path=SixPanelIndependentOuterCaptureRunner(
            plan=load_plan(),base_protocol=load_protocol(),
            client_id=app["client_id"],client_secret=app["client_secret"],access_token=token,
            config=config,repo_root=ROOT,
        ).run()
        print("UPLOAD THIS ONE ZIP BACK INTO THE GPT/DIRECTOR CHAT. DO NOT MODIFY GITHUB:")
        print(path)
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print("[CAPTURE BLOCKED SAFELY]",redact_text(str(exc))); raise SystemExit(1) from None
