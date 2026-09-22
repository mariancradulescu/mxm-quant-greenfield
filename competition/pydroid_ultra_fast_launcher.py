"""One-button Pydroid launcher for ultra-fast friction-qualified Stage-A capture."""
from __future__ import annotations
import inspect,json
from pathlib import Path
from m6.ctrader_capture import CaptureContractError,FORBIDDEN_MUTATION_PROTO_REQUESTS,require_read_only_request,redact_text
from m6.pydroid_oauth import ACCOUNT_SELECTION_PATH,choose_live_account_locally,ensure_v2_authorization,load_saved_account_id
from m6.ctrader_proto.OpenApiModelMessages_pb2 import ProtoOATrendbarPeriod
from m6.ctrader_proto.OpenApiMessages_pb2 import ProtoOAGetTrendbarsRes
from .ultra_fast_capture import UltraFastCaptureRunner,PLAN_REL,PROTOCOL_REL,validate_plan,friction_windows

ROOT=Path(__file__).resolve().parents[1]
ALLOWED=frozenset({"ProtoOAApplicationAuthReq","ProtoOAGetAccountListByAccessTokenReq","ProtoOAAccountAuthReq","ProtoOATraderReq","ProtoOAAssetListReq","ProtoOASymbolsListReq","ProtoOASymbolByIdReq","ProtoOASymbolsForConversionReq","ProtoOAGetTickDataReq","ProtoOAGetTrendbarsReq"})

def load_authorities():
    plan=json.loads((ROOT/PLAN_REL).read_text(encoding="utf-8"))
    protocol=json.loads((ROOT/PROTOCOL_REL).read_text(encoding="utf-8"))
    validate_plan(plan,protocol)
    return plan,protocol

def local_preflight():
    plan,protocol=load_authorities()
    for name in ALLOWED:require_read_only_request(name)
    for name in FORBIDDEN_MUTATION_PROTO_REQUESTS:
        try:require_read_only_request(name)
        except CaptureContractError:pass
        else:raise CaptureContractError(f"mutation unexpectedly allowed: {name}")
    if ProtoOATrendbarPeriod.Value("M5")!=5:raise CaptureContractError("unexpected cTrader M5 enum")
    source=inspect.getsource(__import__("competition.ultra_fast_capture",fromlist=["*"]))
    for forbidden in ("ProtoOANewOrderReq","ProtoOACancelOrderReq","ProtoOAClosePositionReq"):
        if forbidden in source:raise CaptureContractError(f"forbidden trading token in capture runtime: {forbidden}")
    return {
      "plan_sha256":plan["plan_sha256"],"shortlist":len(plan["shortlist"]),"max_stage_a_markets":plan["max_stage_a_markets"],
      "global_windows":len(friction_windows(protocol,"GLOBAL_24X5")),"crypto_windows":len(friction_windows(protocol,"CRYPTO_24X7")),
      "regional_windows":len(friction_windows(protocol,"US_REGIONAL")),"stage_a_interval":plan["stage_a_interval"],
      "raw_ticks_transferred":False,"network_connection_attempted":False,"credentials_used":False,"orders_permitted":False,
      "account_mutation_permitted":False,"economic_outcomes_opened":False
    }

def main():
    print("MXM Ultra-Fast Competition Discovery V4 | READ ONLY | trendbar-pagination=VERSION_COMPATIBLE | friction-checkpoint=RESUMABLE | Stage-A=13 complete weeks M5")
    try:
        print("[PREFLIGHT PASS]",local_preflight())
        app,token,mode=ensure_v2_authorization();print("[OAUTH]",mode)
        config={"ctid_trader_account_id":load_saved_account_id(),"account_selection_path":str(ACCOUNT_SELECTION_PATH),"account_selector":choose_live_account_locally}
        plan,protocol=load_authorities()
        path=UltraFastCaptureRunner(plan=plan,protocol=protocol,client_id=app["client_id"],client_secret=app["client_secret"],access_token=token,config=config,repo_root=ROOT).run()
        print("RETURN THIS ONE ZIP TO CHATGPT:");print(path)
    except KeyboardInterrupt:raise SystemExit(130)
    except Exception as exc:
        print("[CAPTURE BLOCKED SAFELY]",redact_text(str(exc)));raise SystemExit(1) from None
