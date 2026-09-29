"""Read-only Pydroid entry point for the frozen high-quality missing delta."""
from pathlib import Path

from m6.ctrader_capture import CaptureContractError, FORBIDDEN_MUTATION_PROTO_REQUESTS, require_read_only_request, redact_text
from m6.pydroid_oauth import ACCOUNT_SELECTION_PATH, choose_live_account_locally, ensure_v2_authorization, load_saved_account_id
from research_core_v3.delta_collector import DeltaCollector, frozen_scope

ROOT=Path(__file__).resolve().parents[1]
ALLOWED=('ProtoOAApplicationAuthReq','ProtoOAGetAccountListByAccessTokenReq',
         'ProtoOAAccountAuthReq','ProtoOATraderReq','ProtoOASymbolsListReq',
         'ProtoOASymbolByIdReq','ProtoOAGetTrendbarsReq')

def main():
    try:
        for name in ALLOWED:require_read_only_request(name)
        for name in FORBIDDEN_MUTATION_PROTO_REQUESTS:
            try:require_read_only_request(name)
            except CaptureContractError:pass
            else:raise CaptureContractError('mutation unexpectedly allowed')
        frozen,_,delta=frozen_scope(ROOT)
        print(f'[PREFLIGHT PASS] frozen primary core={frozen["primary_count"]}; reused={frozen["reused_count"]}; collect only missing={len(delta)}; read-only')
        app,token,mode=ensure_v2_authorization();print('[OAUTH]',mode)
        config={'ctid_trader_account_id':load_saved_account_id(),
                'account_selection_path':str(ACCOUNT_SELECTION_PATH),
                'account_selector':choose_live_account_locally}
        path=DeltaCollector(client_id=app['client_id'],client_secret=app['client_secret'],
                            access_token=token,config=config,repo_root=ROOT).run()
        print('UPLOAD THIS ONE ZIP BACK TO CHATGPT:',path)
    except KeyboardInterrupt:raise SystemExit(130)
    except Exception as exc:
        print('[CAPTURE PAUSED; RESTART TO RESUME]',redact_text(str(exc)))
        raise SystemExit(1) from None

if __name__=='__main__':main()
