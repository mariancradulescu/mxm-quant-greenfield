from __future__ import annotations
import inspect
from pathlib import Path
from m6.ctrader_capture import CaptureContractError, FORBIDDEN_MUTATION_PROTO_REQUESTS, require_read_only_request, redact_text
from m6.pydroid_oauth import ACCOUNT_SELECTION_PATH, choose_live_account_locally, ensure_v2_authorization, load_saved_account_id
from research_core_v3.adaptive_collector import AdaptiveCollector, frontier

ROOT=Path(__file__).resolve().parents[1]
ALLOWED=('ProtoOAApplicationAuthReq','ProtoOAGetAccountListByAccessTokenReq','ProtoOAAccountAuthReq','ProtoOATraderReq','ProtoOASymbolsListReq','ProtoOASymbolByIdReq','ProtoOAGetTrendbarsReq')
def preflight():
    for name in ALLOWED:require_read_only_request(name)
    for name in FORBIDDEN_MUTATION_PROTO_REQUESTS:
        try:require_read_only_request(name)
        except CaptureContractError:pass
        else:raise CaptureContractError('mutation unexpectedly allowed')
    source=inspect.getsource(__import__('research_core_v3.adaptive_collector',fromlist=['*']))
    for forbidden in ('ProtoOANewOrderReq','ProtoOACancelOrderReq','ProtoOAClosePositionReq','ProtoOAAmendOrderReq'):
        if forbidden in source:raise CaptureContractError('forbidden trading token')
    identities,_=frontier(ROOT)
    print(f'[PREFLIGHT PASS] {len(identities)} exact Pepperstone frontier identities; read-only; no fixed symbol panel')
def main():
    try:
        preflight()
        app,token,mode=ensure_v2_authorization();print('[OAUTH]',mode)
        config={'ctid_trader_account_id':load_saved_account_id(),'account_selection_path':str(ACCOUNT_SELECTION_PATH),'account_selector':choose_live_account_locally}
        path=AdaptiveCollector(client_id=app['client_id'],client_secret=app['client_secret'],access_token=token,config=config,repo_root=ROOT).run()
        print('UPLOAD THIS ONE ZIP BACK TO CHATGPT:',path)
    except KeyboardInterrupt:raise SystemExit(130)
    except Exception as exc:
        print('[CAPTURE PAUSED; RESTART TO RESUME]',redact_text(str(exc)))
        raise SystemExit(1) from None
if __name__=='__main__':main()
