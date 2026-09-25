"""One-button Android launcher for Epoch22 replacement-representative M5 capture."""
from __future__ import annotations
import inspect,json
from pathlib import Path
from m6.ctrader_capture import CaptureContractError,FORBIDDEN_MUTATION_PROTO_REQUESTS,require_read_only_request,redact_text
from m6.pydroid_oauth import ACCOUNT_SELECTION_PATH,choose_live_account_locally,ensure_v2_authorization,load_saved_account_id
from research_v3.current_frontier_replacement_development_capture import (
    CurrentFrontierReplacementDevelopmentRunner,PLAN_REL,validate_plan,
)
ROOT=Path(__file__).resolve().parents[1]
ALLOWED=frozenset({"ProtoOAApplicationAuthReq","ProtoOAGetAccountListByAccessTokenReq","ProtoOAAccountAuthReq","ProtoOATraderReq","ProtoOASymbolsListReq","ProtoOASymbolByIdReq","ProtoOAGetTrendbarsReq"})
def load_plan():
    plan=json.loads((ROOT/PLAN_REL).read_text(encoding="utf-8"));validate_plan(plan);return plan
def local_preflight():
    for name in ALLOWED:require_read_only_request(name)
    for name in FORBIDDEN_MUTATION_PROTO_REQUESTS:
        try:require_read_only_request(name)
        except CaptureContractError:pass
        else:raise CaptureContractError(f"mutation unexpectedly allowed: {name}")
    source=inspect.getsource(__import__("research_v3.current_frontier_replacement_development_capture",fromlist=["*"]))
    for forbidden in ("ProtoOANewOrderReq","ProtoOACancelOrderReq","ProtoOAClosePositionReq","ProtoOAAmendOrderReq"):
        if forbidden in source:raise CaptureContractError(f"forbidden trading token: {forbidden}")
    p=load_plan()
    return {"plan_sha256":p["plan_sha256"],"symbols":len(p["symbols"]),"resolution":p["resolution"],"interval":p["interval"],
            "network_connection_attempted":False,"credentials_used":False,"orders_permitted":False,"account_mutation_permitted":False,
            "economic_outcomes_opened":False,"v2_attempts_consumed":False}
def main():
    print("MXM Epoch22 current-frontier replacement history | READ ONLY | economics=NO | protected=NO")
    try:
        print("[PREFLIGHT PASS]",local_preflight())
        app,token,mode=ensure_v2_authorization();print("[OAUTH]",mode)
        config={"ctid_trader_account_id":load_saved_account_id(),"account_selection_path":str(ACCOUNT_SELECTION_PATH),"account_selector":choose_live_account_locally}
        path=CurrentFrontierReplacementDevelopmentRunner(plan=load_plan(),client_id=app["client_id"],client_secret=app["client_secret"],access_token=token,config=config,repo_root=ROOT).run()
        print("UPLOAD THIS ONE ZIP BACK TO CHATGPT:");print(path)
    except KeyboardInterrupt:raise SystemExit(130)
    except Exception as exc:
        print("[CAPTURE BLOCKED SAFELY]",redact_text(str(exc)));raise SystemExit(1) from None
if __name__=="__main__":main()
