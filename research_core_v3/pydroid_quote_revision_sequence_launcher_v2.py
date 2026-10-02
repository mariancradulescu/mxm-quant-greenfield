"""One-button Pydroid launcher for the frozen quote-revision-sequence V2 raw capture."""
from __future__ import annotations

import inspect
from pathlib import Path

from m6.ctrader_capture import (
    CaptureContractError,
    FORBIDDEN_MUTATION_PROTO_REQUESTS,
    require_read_only_request,
    redact_text,
)
from m6.pydroid_oauth import (
    ACCOUNT_SELECTION_PATH,
    choose_live_account_locally,
    ensure_v2_authorization,
    load_saved_account_id,
)
from research_core_v3.quote_revision_sequence_raw_capture_v2 import (
    QuoteRevisionRawRunner,
    load_plan,
)

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = frozenset({
    "ProtoOAApplicationAuthReq",
    "ProtoOAGetAccountListByAccessTokenReq",
    "ProtoOAAccountAuthReq",
    "ProtoOATraderReq",
    "ProtoOAAssetListReq",
    "ProtoOASymbolsListReq",
    "ProtoOASymbolByIdReq",
    "ProtoOAExpectedMarginReq",
    "ProtoOAGetTickDataReq",
})


def local_preflight():
    for name in ALLOWED:
        require_read_only_request(name)
    for name in FORBIDDEN_MUTATION_PROTO_REQUESTS:
        try:
            require_read_only_request(name)
        except CaptureContractError:
            pass
        else:
            raise CaptureContractError(f"mutation unexpectedly allowed: {name}")
    source = inspect.getsource(
        __import__(
            "research_core_v3.quote_revision_sequence_raw_capture_v2",
            fromlist=["*"],
        )
    )
    forbidden = (
        "ProtoOANewOrderReq",
        "ProtoOACancelOrderReq",
        "ProtoOAClosePositionReq",
        "ProtoOAAmendOrderReq",
        "ProtoOAAmendPositionSLTPReq",
        "ProtoOASubscribeSpotsReq",
        "ProtoOAUnsubscribeSpotsReq",
    )
    for token in forbidden:
        if token in source:
            raise CaptureContractError(f"forbidden trading/live-forward token in collector: {token}")
    plan = load_plan(ROOT)
    return {
        "schema": plan["schema"],
        "signal_symbols": [x["symbol"] for x in plan["signal_symbols"]],
        "dates": len(plan["calendar"]["dates_utc"]),
        "windows": plan["calendar"]["windows_utc"],
        "network_connection_attempted": False,
        "credentials_used": False,
        "orders_permitted": False,
        "account_mutation_permitted": False,
        "device_strategy_features": False,
        "device_strategy_outcomes": False,
        "device_pnl": False,
        "protected_forward_opened": False,
    }


def main():
    print("MXM V3 Quote Revision Sequence V2 | READ ONLY | LOSSLESS RAW BID/ASK ONLY")
    try:
        print("[LOCAL PREFLIGHT PASS]", local_preflight())
        app, token, mode = ensure_v2_authorization()
        print("[OAUTH]", mode)
        config = {
            "ctid_trader_account_id": load_saved_account_id(),
            "account_selection_path": str(ACCOUNT_SELECTION_PATH),
            "account_selector": choose_live_account_locally,
        }
        path = QuoteRevisionRawRunner(
            plan=load_plan(ROOT),
            client_id=app["client_id"],
            client_secret=app["client_secret"],
            access_token=token,
            config=config,
            repo_root=ROOT,
        ).run()
        print("RETURN THIS ONE ZIP TO CHATGPT:")
        print(path)
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print("[CAPTURE BLOCKED SAFELY]", redact_text(str(exc)))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
