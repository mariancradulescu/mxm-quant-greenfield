"""One-button Android launcher for the single generic broker-universe capture."""
from __future__ import annotations
import inspect
from pathlib import Path
from m6.ctrader_capture import CaptureContractError,FORBIDDEN_MUTATION_PROTO_REQUESTS,require_read_only_request,redact_text
from m6.pydroid_oauth import ACCOUNT_SELECTION_PATH,choose_live_account_locally,ensure_v2_authorization,load_saved_account_id
from .broker_universe_capture_v3 import BrokerUniverseCaptureRunnerV3

ROOT=Path(__file__).resolve().parents[1]
ALLOWED=frozenset({"ProtoOAApplicationAuthReq","ProtoOAGetAccountListByAccessTokenReq","ProtoOAAccountAuthReq","ProtoOATraderReq","ProtoOAAssetListReq","ProtoOAAssetClassListReq","ProtoOASymbolCategoryListReq","ProtoOASymbolsListReq","ProtoOASymbolByIdReq","ProtoOAExpectedMarginReq","ProtoOAGetDynamicLeverageByIDReq","ProtoOAMarginCallListReq"})

def local_preflight():
    for name in ALLOWED:require_read_only_request(name)
    for name in FORBIDDEN_MUTATION_PROTO_REQUESTS:
        try:require_read_only_request(name)
        except CaptureContractError:pass
        else:raise CaptureContractError(f"mutation unexpectedly allowed: {name}")
    source=inspect.getsource(__import__("competition.broker_universe_capture_v3",fromlist=["*"]))
    for forbidden in ("ProtoOANewOrderReq","ProtoOACancelOrderReq","ProtoOAClosePositionReq"):
        if forbidden in source:raise CaptureContractError(f"forbidden trading token: {forbidden}")
    return {"network_connection_attempted":False,"credentials_used":False,"orders_permitted":False,"account_mutation_permitted":False}

def main():
    print("MXM Competition broker-native universe | READ ONLY | economics=NO | protected=NO")
    try:
        print("[PREFLIGHT PASS]",local_preflight())
        app,token,mode=ensure_v2_authorization();print("[OAUTH]",mode)
        config={"ctid_trader_account_id":load_saved_account_id(),"account_selection_path":str(ACCOUNT_SELECTION_PATH),"account_selector":choose_live_account_locally}
        path=BrokerUniverseCaptureRunnerV3(client_id=app["client_id"],client_secret=app["client_secret"],access_token=token,config=config,repo_root=ROOT).run()
        print("RETURN THIS ONE ZIP TO CHATGPT:");print(path)
    except KeyboardInterrupt:raise SystemExit(130)
    except Exception as exc:
        print("[CAPTURE BLOCKED SAFELY]",redact_text(str(exc)));raise SystemExit(1) from None
