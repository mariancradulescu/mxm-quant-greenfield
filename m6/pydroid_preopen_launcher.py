"""One-button Android launcher for the PRE-M6 09:30 pre-open supplement."""
from __future__ import annotations
import json
import socket
import tempfile
import zipfile
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path
from urllib.parse import urlparse

from .cost_evidence import TIER1_SYMBOLS, sha256_file
from .ctrader_capture import CaptureContractError, READ_ONLY_SCOPE, is_loopback_redirect, redact_text, require_read_only_request
from .pydroid_oauth import ACCOUNT_SELECTION_PATH, PRIVATE_ROOT, REDIRECT_URI, choose_live_account_locally, ensure_v2_authorization, load_saved_account_id
from .preopen_supplement import PREOPEN_PLAN_REL, signal_blind_preopen_windows

ROOT=Path(__file__).resolve().parents[1]
PLAN_PATH=ROOT/PREOPEN_PLAN_REL
OUTPUT_ROOT=ROOT/"preopen_capture_output"
WORK_ROOT=ROOT/".m6_cost_evidence_work"

def _require_versions():
    try: actual=package_version("protobuf")
    except PackageNotFoundError as exc:
        raise CaptureContractError("missing protobuf 3.20.1; rerun M6_PREOPEN_SUPPLEMENT_RUN.py") from exc
    if actual!="3.20.1":
        raise CaptureContractError(f"protobuf {actual} incompatible; required 3.20.1")
    return actual

def _probe(path):
    path.mkdir(parents=True,exist_ok=True)
    p=path/".mxm_preopen_probe"; p.write_text("MXM",encoding="utf-8")
    if p.read_text(encoding="utf-8")!="MXM": raise CaptureContractError(f"directory is not writable: {path}")
    p.unlink(missing_ok=True)

def _callback():
    if not is_loopback_redirect(REDIRECT_URI): raise CaptureContractError("OAuth redirect must remain loopback-only")
    u=urlparse(REDIRECT_URI)
    try:
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind((u.hostname,int(u.port)))
    except OSError: return {"available":False}
    return {"available":True}

def local_preflight():
    version=_require_versions()
    plan=json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    if plan.get("status")!="FROZEN_PRE_OUTCOME_INCREMENTAL_SIGNAL_BLIND":
        raise CaptureContractError("pre-open supplement plan is not active/frozen")
    if set(plan["targets"])!={"US500","NAS100"}: raise CaptureContractError("pre-open target set changed")
    for k,v in TIER1_SYMBOLS.items():
        if int(plan["targets"][k]["symbol_id"])!=int(v["symbol_id"]): raise CaptureContractError(f"{k} symbolId changed")
    require_read_only_request("ProtoOAGetTickDataReq")
    windows=signal_blind_preopen_windows()
    _probe(OUTPUT_ROOT); _probe(WORK_ROOT); _probe(PRIVATE_ROOT)
    with tempfile.TemporaryDirectory(prefix="mxm_preopen_") as td:
        z=Path(td)/"p.zip"
        with zipfile.ZipFile(z,"w") as fh: fh.writestr("probe.txt",b"MXM")
        if len(sha256_file(z))!=64: raise CaptureContractError("ZIP/SHA preflight failed")
    old=ROOT/".m6_cost_evidence_work"/"tier1_us500_nas100_v3"/"chunks"
    if not old.is_dir(): raise CaptureContractError("preserved Tier-1 V3 chunks are required and were not found")
    return {"protobuf":version,"windows":len(windows),"callback":_callback(),"scope":READ_ONLY_SCOPE}

def main():
    print("MXM Quant Greenfield V2 — PRE-M6 09:30 incremental supplement")
    print("Contract: accounts/view-only | 09:15-09:30 ET only | US500=127 + NAS100=126 | orders=NO | economics=NO")
    print("The accepted 09:30-16:00 Tier-1 capture is NOT rerun. Existing V3 chunks are read locally only for deterministic generic cost support.")
    try: report=local_preflight()
    except Exception as exc:
        print("[PREFLIGHT FAIL]",redact_text(str(exc))); raise SystemExit(2) from None
    print(f"[PREFLIGHT PASS] protobuf {report['protobuf']} | weekday windows={report['windows']} | scope=accounts")
    try: app,token,mode=ensure_v2_authorization()
    except Exception as exc:
        print("OAuth BLOCKED safely:",redact_text(str(exc))); raise SystemExit(1) from None
    print(f"[OAUTH] {mode}; saved authorization is reused/refreshed when safe.")
    config={"ctid_trader_account_id":load_saved_account_id(),"account_selection_path":str(ACCOUNT_SELECTION_PATH),"account_selector":choose_live_account_locally}
    try:
        from .preopen_evidence_openapi import PreopenSupplementRunner
        path=PreopenSupplementRunner(client_id=app["client_id"],client_secret=app["client_secret"],access_token=token,config=config,repo_root=ROOT).run()
    except KeyboardInterrupt:
        print("\n[PAUSED] Progress is resumable. Run this SAME file again."); raise SystemExit(130) from None
    except Exception as exc:
        print("\n[PREOPEN BLOCKED SAFELY]",redact_text(str(exc)))
        print("No order/account mutation/economic outcome occurred. Rerun the same file to resume.")
        raise SystemExit(1) from None
    finally:
        token=None
    print("\nPREOPEN SUPPLEMENT COMPLETE.")
    print("Return ONLY this ZIP to ChatGPT:")
    print(path)
    print("Do NOT delete either .m6_cost_evidence_work directory.")

if __name__=="__main__": main()
