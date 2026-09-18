"""One-button Android launcher for bounded PRE-M6 Tier-1 BID/ASK cost evidence."""
from __future__ import annotations

import json
import socket
import tempfile
import zipfile
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path
from urllib.parse import urlparse

from .cost_evidence import TIER1_SYMBOLS, signal_blind_cash_session_windows
from .ctrader_capture import (
    READ_ONLY_SCOPE,
    CaptureContractError,
    is_loopback_redirect,
    redact_text,
    require_read_only_request,
    sha256_file,
)
from .pydroid_oauth import (
    ACCOUNT_SELECTION_PATH,
    PRIVATE_ROOT,
    REDIRECT_URI,
    choose_live_account_locally,
    ensure_v2_authorization,
    load_saved_account_id,
)

ROOT=Path(__file__).resolve().parents[1]
PLAN_PATH=ROOT/"data"/"M6_TIER1_COST_EVIDENCE_PLAN_V3.json"
OUTPUT_ROOT=ROOT/"cost_capture_output"
WORK_ROOT=ROOT/".m6_cost_evidence_work"


def _require_versions():
    try:
        actual=package_version("protobuf")
    except PackageNotFoundError as exc:
        raise CaptureContractError("missing protobuf 3.20.1; rerun M6_COST_EVIDENCE_RUN.py") from exc
    if actual!="3.20.1":
        raise CaptureContractError(f"protobuf {actual} incompatible; required 3.20.1")
    return actual


def _probe(path:Path):
    path.mkdir(parents=True,exist_ok=True)
    probe=path/".mxm_cost_write_probe"
    probe.write_text("MXM",encoding="utf-8")
    if probe.read_text(encoding="utf-8")!="MXM":
        raise CaptureContractError(f"directory is not writable: {path}")
    probe.unlink(missing_ok=True)


def _validate_callback_port():
    if not is_loopback_redirect(REDIRECT_URI):
        raise CaptureContractError("OAuth redirect must remain loopback-only")
    parsed=urlparse(REDIRECT_URI)
    try:
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            sock.bind((parsed.hostname,int(parsed.port)))
    except OSError:
        # A saved authorization usually needs no callback. Do not fail merely because an
        # old browser callback listener is finishing; fresh auth will fail safely if needed.
        return {"available":False}
    return {"available":True}


def local_preflight():
    version=_require_versions()
    if not PLAN_PATH.is_file():
        raise CaptureContractError("cost-evidence plan missing")
    plan=json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    if plan.get("status")!="PRE_OUTCOME_QUOTE_EVIDENCE_EXECUTION_AUTHORITY_SEPARATED_READ_ONLY_ACQUISITION_PLAN":
        raise CaptureContractError("Tier-1 V3 cost-evidence plan is not active/frozen")
    if plan.get("oauth_scope")!="accounts" or plan.get("orders") is not False:
        raise CaptureContractError("cost-evidence plan violates read-only contract")
    if set(plan["targets"])!={"US500","NAS100"}:
        raise CaptureContractError("cost-evidence target set changed")
    for canonical,expected in TIER1_SYMBOLS.items():
        target=plan["targets"][canonical]
        if int(target["symbol_id"])!=int(expected["symbol_id"]):
            raise CaptureContractError(f"{canonical} accepted symbolId changed")
    require_read_only_request("ProtoOAGetTickDataReq")
    windows=signal_blind_cash_session_windows()
    if not windows:
        raise CaptureContractError("cost-evidence session plan empty")
    _probe(OUTPUT_ROOT); _probe(WORK_ROOT); _probe(PRIVATE_ROOT)
    callback=_validate_callback_port()
    with tempfile.TemporaryDirectory(prefix="mxm_cost_preflight_") as td:
        p=Path(td)/"probe.zip"
        with zipfile.ZipFile(p,"w",compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("probe.txt",b"MXM")
        if len(sha256_file(p))!=64:
            raise CaptureContractError("ZIP/SHA preflight failed")
    return {
        "protobuf":version,
        "windows":len(windows),
        "callback":callback,
        "scope":READ_ONLY_SCOPE,
        "targets":{k:v["symbol_id"] for k,v in TIER1_SYMBOLS.items()},
    }


def main():
    print("MXM Quant Greenfield V2 — PRE-M6 Tier-1 V3 historical BID/ASK quote evidence")
    print("Contract: accounts/view-only | US500=127 + NAS100=126 | orders=NO | economics=NO")
    print("Existing OHLC capture is NOT rerun. Quote evidence is NOT an automatic fill rule.")

    try:
        report=local_preflight()
    except Exception as exc:
        print("[PREFLIGHT FAIL]",redact_text(str(exc)))
        raise SystemExit(2) from None
    print(
        f"[PREFLIGHT PASS] protobuf {report['protobuf']} | "
        f"weekday session windows={report['windows']} | scope=accounts | historical ticks read-only"
    )

    try:
        app,access_token,auth_mode=ensure_v2_authorization()
    except Exception as exc:
        print("OAuth BLOCKED safely:",redact_text(str(exc)))
        raise SystemExit(1) from None
    print(f"[OAUTH] {auth_mode}; saved authorization is reused/refreshed when safe.")

    config={
        "ctid_trader_account_id":load_saved_account_id(),
        "account_selection_path":str(ACCOUNT_SELECTION_PATH),
        "account_selector":choose_live_account_locally,
    }
    try:
        from .cost_evidence_openapi import CostEvidenceRunner
        runner=CostEvidenceRunner(
            client_id=app["client_id"],
            client_secret=app["client_secret"],
            access_token=access_token,
            config=config,
            repo_root=ROOT,
        )
        zip_path=runner.run()
    except KeyboardInterrupt:
        print("\n[PAUSED] Progress is resumable. Run this SAME file again to continue.")
        raise SystemExit(130) from None
    except Exception as exc:
        print("\n[COST CAPTURE BLOCKED SAFELY]",redact_text(str(exc)))
        print("No order/account mutation/economic outcome occurred. Rerun the same file to resume.")
        raise SystemExit(1) from None
    finally:
        access_token=None

    print("\nCOST EVIDENCE CAPTURE COMPLETE.")
    print("Return ONLY this ZIP to ChatGPT:")
    print(zip_path)
    print("Do not send ~/.mxm_quant/ or .m6_cost_evidence_work/.")
