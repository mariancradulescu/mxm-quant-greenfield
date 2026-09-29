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
from research_core_v3.collector import V3PepperstoneM5Runner, build_wave0_plan

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = frozenset(
    {
        "ProtoOAApplicationAuthReq",
        "ProtoOAGetAccountListByAccessTokenReq",
        "ProtoOAAccountAuthReq",
        "ProtoOATraderReq",
        "ProtoOASymbolsListReq",
        "ProtoOASymbolByIdReq",
        "ProtoOAGetTrendbarsReq",
    }
)


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
    source = inspect.getsource(__import__("research_core_v3.collector", fromlist=["*"]))
    for forbidden in (
        "ProtoOANewOrderReq",
        "ProtoOACancelOrderReq",
        "ProtoOAClosePositionReq",
        "ProtoOAAmendOrderReq",
    ):
        if forbidden in source:
            raise CaptureContractError(f"forbidden trading token: {forbidden}")
    plan = build_wave0_plan(ROOT)
    return {
        "schema": plan["schema"],
        "plan_sha256": plan["plan_sha256"],
        "wave_index": plan["wave_index"],
        "symbols": len(plan["symbols"]),
        "cohorts": plan["structural_cohort_count"],
        "resolution": plan["resolution"],
        "interval": plan["interval"],
        "network_connection_attempted": False,
        "credentials_used": False,
        "orders_permitted": False,
        "account_mutation_permitted": False,
        "protected_forward_opened": False,
        "economic_outcomes_opened": 0,
    }


def main():
    print("MXM Research Core V3 Pepperstone M5 Wave00 | READ ONLY | DEVELOPMENT ONLY")
    try:
        print("[PREFLIGHT PASS]", local_preflight())
        app, token, mode = ensure_v2_authorization()
        print("[OAUTH]", mode)
        config = {
            "ctid_trader_account_id": load_saved_account_id(),
            "account_selection_path": str(ACCOUNT_SELECTION_PATH),
            "account_selector": choose_live_account_locally,
        }
        plan = build_wave0_plan(ROOT)
        path = V3PepperstoneM5Runner(
            plan=plan,
            client_id=app["client_id"],
            client_secret=app["client_secret"],
            access_token=token,
            config=config,
            repo_root=ROOT,
        ).run()
        print("UPLOAD THIS ONE ZIP BACK TO CHATGPT:")
        print(path)
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print("[V3 CAPTURE BLOCKED SAFELY]", redact_text(str(exc)))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
