"""Active Pydroid launcher for the Android-safe M6 cTrader capture."""
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
    EXPECTED_PLAN_SHA,
    FORBIDDEN_MUTATION_PROTO_REQUESTS,
    READ_ONLY_PROTO_REQUESTS,
    READ_ONLY_SCOPE,
    CaptureContractError,
    is_loopback_redirect,
    redact_text,
    require_read_only_request,
    scan_bundle_for_secrets,
    sha256_file,
    validate_capture_plan,
)
from .pydroid_oauth import (
    ACCOUNT_SELECTION_PATH,
    PRIVATE_ROOT,
    REDIRECT_URI,
    choose_live_account_locally,
    ensure_v2_authorization,
    load_saved_account_id,
)
from .pydroid_symbol_mapping import (
    choose_symbol_locally,
    clear_symbol_override,
    load_symbol_overrides,
    save_symbol_override,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "data" / "PRIMARY_WAVE_02_MATERIALIZATION_PLAN_V2.json"
OUTPUT_ROOT = ROOT / "capture_output"
WORK_ROOT = ROOT / ".m6_capture_work"


def _require_versions():
    try:
        actual = package_version("protobuf")
    except PackageNotFoundError as exc:
        raise CaptureContractError("missing protobuf 3.20.1; rerun M6_CAPTURE_RUN.py") from exc
    if actual != "3.20.1":
        raise CaptureContractError(
            f"protobuf version {actual} is incompatible; required exactly 3.20.1"
        )
    return {"protobuf": actual}


def _probe_writable_directory(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    probe = path / ".mxm_write_probe"
    try:
        probe.write_bytes(b"MXM")
        if probe.read_bytes() != b"MXM":
            raise OSError("write/read mismatch")
    except OSError as exc:
        raise CaptureContractError(f"directory is not writable: {path}") from exc
    finally:
        probe.unlink(missing_ok=True)


def _validate_callback_port():
    if not is_loopback_redirect(REDIRECT_URI):
        raise CaptureContractError("V2 requires http://127.0.0.1:8765/callback")
    parsed = urlparse(REDIRECT_URI)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((parsed.hostname, int(parsed.port)))
    except OSError as exc:
        raise CaptureContractError(
            f"OAuth callback port {parsed.hostname}:{parsed.port} cannot be bound; "
            "close the app using that port and RUN again"
        ) from exc
    return {"host": parsed.hostname, "port": parsed.port, "path": parsed.path}


def local_preflight():
    versions = _require_versions()
    if not PLAN_PATH.is_file():
        raise CaptureContractError(f"missing frozen plan: {PLAN_PATH}")
    try:
        plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CaptureContractError("frozen plan is unreadable or malformed JSON") from exc
    plan_result = validate_capture_plan(plan)
    if plan.get("plan_sha256") != EXPECTED_PLAN_SHA:
        raise CaptureContractError("frozen plan SHA authority changed")

    _probe_writable_directory(OUTPUT_ROOT)
    _probe_writable_directory(WORK_ROOT)
    _probe_writable_directory(PRIVATE_ROOT)
    callback = _validate_callback_port()

    for proto_name in READ_ONLY_PROTO_REQUESTS:
        require_read_only_request(proto_name)
    for proto_name in FORBIDDEN_MUTATION_PROTO_REQUESTS:
        try:
            require_read_only_request(proto_name)
        except CaptureContractError:
            pass
        else:
            raise CaptureContractError(
                f"mutation request unexpectedly permitted: {proto_name}"
            )

    with tempfile.TemporaryDirectory(prefix="mxm_m6_preflight_") as td:
        temp = Path(td)
        test_bundle = temp / "bundle"
        test_bundle.mkdir()
        (test_bundle / "probe.txt").write_text("preflight-safe\n", encoding="utf-8")
        scan_bundle_for_secrets(test_bundle, ["MXM_PREFLIGHT_SECRET_DO_NOT_WRITE"])
        package_probe = temp / "zip_probe.zip"
        with zipfile.ZipFile(package_probe, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("probe.txt", b"MXM")
        if len(sha256_file(package_probe)) != 64:
            raise CaptureContractError("ZIP/SHA256 preflight failed")

    from . import ctrader_openapi
    transport = ctrader_openapi.runtime_sdk_preflight()
    if transport.get("network_connection_attempted") is not False:
        raise CaptureContractError("runtime preflight unexpectedly used network")
    if transport.get("credentials_used") is not False:
        raise CaptureContractError("runtime preflight unexpectedly used credentials")
    if transport.get("cryptography_required") is not False:
        raise CaptureContractError("Android runtime unexpectedly requires cryptography")
    if transport.get("rust_required") is not False:
        raise CaptureContractError("Android runtime unexpectedly requires Rust")

    source = inspect.getsource(ctrader_openapi)
    for token in (
        "ProtoOANewOrderReq",
        "ProtoOACancelOrderReq",
        "ProtoOAClosePositionReq",
        "ProtoOAAmendOrderReq",
        'scope="trading"',
        "scope='trading'",
    ):
        if token in source:
            raise CaptureContractError(
                f"runtime adapter contains forbidden trading/mutation token: {token}"
            )

    return plan, {
        "packages": versions,
        "plan": plan_result,
        "callback": callback,
        "transport": transport,
        "scope": READ_ONLY_SCOPE,
        "orders_permitted": False,
        "account_mutation_permitted": False,
        "cryptography_required": False,
        "rust_required": False,
    }


def main():
    print("MXM Quant Greenfield V2 — M6 read-only cTrader DEVELOPMENT capture")
    print(
        "Contract: scope=accounts | target=Pepperstone LIVE | "
        "orders=NO | account mutation=NO | economics=NO"
    )
    print("Android runtime: stdlib TLS/socket + official cTrader protobuf messages")

    print("\n[LOCAL PREFLIGHT] Validating Android-safe runtime before authorization...")
    try:
        plan, report = local_preflight()
    except Exception as exc:
        print("[PREFLIGHT FAIL]", redact_text(str(exc)))
        print("STOPPED before OAuth and before broker capture.")
        raise SystemExit(2) from None

    print(
        "[PREFLIGHT PASS] protobuf | frozen plan/hash | writable paths | callback | "
        "ZIP/SHA | accounts/read-only | stdlib TLS/protobuf heartbeat"
    )
    print(
        f"[PREFLIGHT PASS] protobuf {report['packages']['protobuf']} | "
        f"LIVE {report['transport']['live_host']}:{report['transport']['live_port']} | "
        "Twisted=NO | cryptography=NO | Rust=NO"
    )

    try:
        app, access_token, auth_mode = ensure_v2_authorization()
    except Exception as exc:
        print("OAuth BLOCKED safely:", redact_text(str(exc)))
        raise SystemExit(1) from None

    if auth_mode == "REUSED_SAVED_ACCESS_TOKEN":
        print("[OAUTH] Saved authorization reused. Browser/login not required.")
    elif auth_mode == "REFRESHED_SAVED_ACCESS_TOKEN":
        print("[OAUTH] Saved authorization refreshed automatically. Browser/login not required.")
    else:
        print("[OAUTH] First authorization saved locally for automatic future reuse.")
    print("[OAUTH] Target=Pepperstone LIVE. DEMO accounts are not eligible for capture.")

    config = {
        "redirect_uri": REDIRECT_URI,
        "ctid_trader_account_id": load_saved_account_id(),
        "account_selection_path": str(ACCOUNT_SELECTION_PATH),
        "account_selector": choose_live_account_locally,
        "symbol_overrides": load_symbol_overrides(),
        "symbol_selector": choose_symbol_locally,
        "symbol_override_saver": save_symbol_override,
        "symbol_override_clearer": clear_symbol_override,
    }

    try:
        from .ctrader_openapi import OpenApiCaptureRunner
        runner = OpenApiCaptureRunner(
            plan=plan,
            client_id=app["client_id"],
            client_secret=app["client_secret"],
            access_token=access_token,
            config=config,
            repo_root=ROOT,
        )
        zip_path = runner.run()
    except Exception as exc:
        print("\nCapture BLOCKED safely:", redact_text(str(exc)))
        print("No order was placed. No M6 economics were run.")
        raise SystemExit(1) from None
    finally:
        access_token = None

    print("\nCAPTURE COMPLETE.")
    print("Return ONLY this ZIP to ChatGPT:")
    print(zip_path)
    print("Do not send anything under ~/.mxm_quant/ or .m6_capture_work/.")
