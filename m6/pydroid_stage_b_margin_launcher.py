"""One-button Android/Pydroid launcher for Stage-B historical margin evidence."""
from __future__ import annotations

import inspect
import json
import socket
import tempfile
import zipfile
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path
from urllib.parse import urlparse

from .ctrader_capture import (
    FORBIDDEN_MUTATION_PROTO_REQUESTS,
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
from .stage_b_margin_evidence import (
    DEVELOPMENT_END_MS,
    MARGIN_HISTORY_PACKAGE_FILES,
    OUTPUT_FILENAME,
    PROTECTED_FORWARD_START_MS,
    TARGET_SYMBOLS,
    initial_windows,
    validate_plan,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "data" / "M6_STAGE_B_MARGIN_HISTORY_SUPPLEMENT_PLAN_V1.json"
OUTPUT_ROOT = ROOT / "stage_b_margin_capture_output"
RAW_LOCAL_ROOT = ROOT / "stage_b_margin_raw_local"

ALLOWED_STAGE_B_MARGIN_REQUESTS = frozenset({
    "ProtoOAApplicationAuthReq",
    "ProtoOAGetAccountListByAccessTokenReq",
    "ProtoOAAccountAuthReq",
    "ProtoOATraderReq",
    "ProtoOASymbolsListReq",
    "ProtoOASymbolByIdReq",
    "ProtoOADealListReq",
    "ProtoOAGetDynamicLeverageByIDReq",
    "ProtoOAMarginCallListReq",
})


def _require_versions() -> str:
    try:
        actual = package_version("protobuf")
    except PackageNotFoundError as exc:
        raise CaptureContractError(
            "missing protobuf 3.20.1; rerun M6_STAGE_B_MARGIN_HISTORY_RUN.py"
        ) from exc
    if actual != "3.20.1":
        raise CaptureContractError(
            f"protobuf {actual} incompatible; required exactly 3.20.1"
        )
    return actual


def _probe(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    probe = path / ".mxm_stage_b_margin_write_probe"
    probe.write_text("MXM", encoding="utf-8")
    if probe.read_text(encoding="utf-8") != "MXM":
        raise CaptureContractError(f"directory is not writable: {path}")
    probe.unlink(missing_ok=True)


def _validate_callback_port() -> dict[str, object]:
    if not is_loopback_redirect(REDIRECT_URI):
        raise CaptureContractError("OAuth redirect must remain loopback-only")
    parsed = urlparse(REDIRECT_URI)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((parsed.hostname, int(parsed.port)))
    except OSError:
        return {
            "available": False,
            "host": parsed.hostname,
            "port": parsed.port,
            "path": parsed.path,
        }
    return {
        "available": True,
        "host": parsed.hostname,
        "port": parsed.port,
        "path": parsed.path,
    }


def local_preflight() -> dict[str, object]:
    version = _require_versions()
    if not PLAN_PATH.is_file():
        raise CaptureContractError("Stage-B historical-margin plan missing")
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    validate_plan(plan)

    if DEVELOPMENT_END_MS >= PROTECTED_FORWARD_START_MS:
        raise CaptureContractError("DEVELOPMENT interval reaches protected-forward boundary")
    windows = initial_windows()
    if not windows:
        raise CaptureContractError("historical deal window plan is empty")

    plan_requests = set(plan.get("read_only_requests") or [])
    if plan_requests != set(ALLOWED_STAGE_B_MARGIN_REQUESTS):
        raise CaptureContractError("frozen Stage-B request allowlist drift")

    for proto_name in sorted(ALLOWED_STAGE_B_MARGIN_REQUESTS):
        require_read_only_request(proto_name)
    for proto_name in sorted(FORBIDDEN_MUTATION_PROTO_REQUESTS):
        try:
            require_read_only_request(proto_name)
        except CaptureContractError:
            pass
        else:
            raise CaptureContractError(
                f"mutation request unexpectedly permitted: {proto_name}"
            )

    _probe(OUTPUT_ROOT)
    _probe(RAW_LOCAL_ROOT)
    _probe(PRIVATE_ROOT)
    callback = _validate_callback_port()

    missing = [
        rel for rel in MARGIN_HISTORY_PACKAGE_FILES
        if not (ROOT / rel).is_file()
    ]
    if missing:
        raise CaptureContractError(
            f"Stage-B historical-margin package incomplete: {missing}"
        )

    from . import stage_b_margin_openapi as runtime
    source = inspect.getsource(runtime)
    for forbidden in (
        "ProtoOANewOrderReq",
        "ProtoOACancelOrderReq",
        "ProtoOAAmendOrderReq",
        "ProtoOAClosePositionReq",
        "ProtoOAAmendPositionSLTPReq",
        'scope="trading"',
        "scope='trading'",
    ):
        if forbidden in source:
            raise CaptureContractError(
                f"Stage-B margin runtime contains forbidden trading token: {forbidden}"
            )

    with tempfile.TemporaryDirectory(prefix="mxm_stage_b_margin_preflight_") as td:
        probe_zip = Path(td) / "probe.zip"
        with zipfile.ZipFile(
            probe_zip, "w", compression=zipfile.ZIP_DEFLATED
        ) as zf:
            zf.writestr("probe.txt", b"MXM")
        if len(sha256_file(probe_zip)) != 64:
            raise CaptureContractError("ZIP/SHA preflight failed")

    return {
        "protobuf": version,
        "scope": READ_ONLY_SCOPE,
        "targets": dict(TARGET_SYMBOLS),
        "initial_windows": len(windows),
        "callback": callback,
        "orders_permitted": False,
        "account_mutation_permitted": False,
        "network_connection_attempted": False,
        "credentials_used": False,
        "output_filename": OUTPUT_FILENAME,
    }


def main() -> None:
    print("MXM Quant Greenfield V2 — Stage-B historical margin evidence")
    print(
        "Contract: Pepperstone Europe LIVE | scope=accounts/view-only | "
        "orders=NO | account mutation=NO | Stage-B economics=NO"
    )
    print("Protected-forward evidence remains CLOSED.")

    print("\n[LOCAL PREFLIGHT] Validating package before OAuth...")
    try:
        report = local_preflight()
    except Exception as exc:
        print("[PREFLIGHT FAIL]", redact_text(str(exc)))
        print("STOPPED before OAuth and before broker capture.")
        raise SystemExit(2) from None

    print(
        f"[PREFLIGHT PASS] protobuf {report['protobuf']} | "
        f"targets={report['targets']} | initial_windows={report['initial_windows']} | "
        "stdlib TLS/protobuf | read-only"
    )

    try:
        app, access_token, auth_mode = ensure_v2_authorization()
    except Exception as exc:
        print("OAuth BLOCKED safely:", redact_text(str(exc)))
        raise SystemExit(1) from None

    if auth_mode == "REUSED_SAVED_ACCESS_TOKEN":
        print("[OAUTH] Saved authorization reused; browser/login not required.")
    elif auth_mode == "REFRESHED_SAVED_ACCESS_TOKEN":
        print("[OAUTH] Saved authorization refreshed automatically.")
    else:
        print("[OAUTH] First view-only authorization saved locally.")
    print("[OAUTH] Target=Pepperstone LIVE; DEMO accounts are not eligible.")

    config = {
        "ctid_trader_account_id": load_saved_account_id(),
        "account_selection_path": str(ACCOUNT_SELECTION_PATH),
        "account_selector": choose_live_account_locally,
    }

    try:
        from .stage_b_margin_openapi import StageBMarginHistoryRunner
        plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        runner = StageBMarginHistoryRunner(
            plan=plan,
            client_id=app["client_id"],
            client_secret=app["client_secret"],
            access_token=access_token,
            config=config,
            repo_root=ROOT,
        )
        zip_path = runner.run()
    except KeyboardInterrupt:
        print("\n[STOPPED] No Stage-B economics or trading request occurred.")
        raise SystemExit(130) from None
    except Exception as exc:
        print("\n[MARGIN CAPTURE BLOCKED SAFELY]", redact_text(str(exc)))
        print(
            "No order/account mutation/Stage-B economic outcome occurred. "
            "Run this same file again after fixing the reported operational issue."
        )
        raise SystemExit(1) from None
    finally:
        access_token = None

    print("\nSTAGE-B HISTORICAL MARGIN EVIDENCE CAPTURE COMPLETE.")
    print("Return ONLY this ZIP to ChatGPT:")
    print(zip_path)
    print(
        "Preserve the stage_b_margin_raw_local folder until ChatGPT explicitly "
        "authorizes deletion."
    )
    print("Do not send ~/.mxm_quant/ or any private OAuth files.")


if __name__ == "__main__":
    main()
