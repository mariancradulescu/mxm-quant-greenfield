"""Active Pydroid launcher/runtime for the M6 read-only cTrader capture."""
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
from .pydroid_oauth import PRIVATE_ROOT, REDIRECT_URI, ensure_v2_authorization

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "data" / "PRIMARY_WAVE_02_MATERIALIZATION_PLAN_V2.json"
OUTPUT_ROOT = ROOT / "capture_output"
WORK_ROOT = ROOT / ".m6_capture_work"


def _require_versions():
    expected_exact = {"ctrader-open-api": "0.9.2", "requests": "2.32.3"}
    found = {}
    for package, expected in expected_exact.items():
        try:
            actual = package_version(package)
        except PackageNotFoundError as exc:
            raise CaptureContractError(
                f"missing required package {package}; run: python -m pip install -r tools/requirements-m6-capture.txt"
            ) from exc
        if actual != expected:
            raise CaptureContractError(
                f"{package} version {actual} is incompatible; required exactly {expected}"
            )
        found[package] = actual
    try:
        service_identity = package_version("service-identity")
    except PackageNotFoundError as exc:
        raise CaptureContractError("missing service-identity; reinstall requirements") from exc
    try:
        major, minor = (int(part) for part in service_identity.split(".")[:2])
    except ValueError as exc:
        raise CaptureContractError(
            f"cannot parse service-identity version {service_identity}"
        ) from exc
    if major != 24 or minor < 1:
        raise CaptureContractError(
            f"service-identity {service_identity} is outside required >=24.1.0,<25"
        )
    found["service-identity"] = service_identity
    return found


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
        raise CaptureContractError(
            "V2 requires approved redirect http://127.0.0.1:8765/callback"
        )
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
    sdk = ctrader_openapi.runtime_sdk_preflight()
    if sdk.get("network_connection_attempted") is not False:
        raise CaptureContractError("runtime SDK preflight unexpectedly used network")
    if sdk.get("credentials_used") is not False:
        raise CaptureContractError("runtime SDK preflight unexpectedly used credentials")

    source = inspect.getsource(ctrader_openapi) + inspect.getsource(ctrader_openapi._base)
    forbidden = (
        "ProtoOANewOrderReq",
        "ProtoOACancelOrderReq",
        "ProtoOAClosePositionReq",
        "ProtoOAAmendOrderReq",
        'scope="trading"',
        "scope='trading'",
    )
    for token in forbidden:
        if token in source:
            raise CaptureContractError(
                f"runtime adapter contains forbidden trading/mutation token: {token}"
            )

    return plan, {
        "packages": versions,
        "plan": plan_result,
        "callback": callback,
        "sdk": sdk,
        "scope": READ_ONLY_SCOPE,
        "orders_permitted": False,
        "account_mutation_permitted": False,
        "output_writable": True,
        "work_writable": True,
        "private_state_writable": True,
        "zip_sha256_operational": True,
        "secret_transfer_probe": "PASS",
    }


def main():
    print("MXM Quant Greenfield V2 — M6 read-only cTrader DEVELOPMENT capture")
    print(
        "Contract: scope=accounts | target=Pepperstone LIVE | "
        "orders=NO | account mutation=NO | economics=NO"
    )

    print("\n[LOCAL PREFLIGHT] Validating pinned runtime before authorization...")
    try:
        plan, report = local_preflight()
    except Exception as exc:
        print("[PREFLIGHT FAIL]", redact_text(str(exc)))
        print("STOPPED before OAuth and before broker capture.")
        raise SystemExit(2) from None

    print(
        "[PREFLIGHT PASS] dependencies | frozen plan/hash | writable paths | "
        "callback | ZIP/SHA | secret boundary | accounts/read-only | SDK heartbeat"
    )
    print(
        f"[PREFLIGHT PASS] cTrader SDK {report['sdk']['ctrader_open_api_version']} | "
        f"LIVE {report['sdk']['live_host']}:{report['sdk']['live_port']} | "
        "network test=NO | credentials used=NO"
    )

    try:
        app, access_token, auth_mode = ensure_v2_authorization()
    except Exception as exc:
        print("OAuth BLOCKED safely:", redact_text(str(exc)))
        raise SystemExit(1) from None

    if auth_mode == "REMEMBERED_V2_AUTHORIZATION":
        print(
            "[OAUTH] Remembered V2 authorization is valid/refreshed. "
            "Browser login not required."
        )
    else:
        print(
            "[OAUTH] Fresh V2 LIVE browser authorization saved privately "
            "for future runs."
        )

    config = {
        "redirect_uri": REDIRECT_URI,
        "ctid_trader_account_id": None,
        "symbol_overrides": {},
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
        print("If a partial ZIP exists in capture_output, return it only for diagnosis.")
        raise SystemExit(1) from None
    finally:
        access_token = None

    print("\nCAPTURE COMPLETE.")
    print("Return ONLY this ZIP to ChatGPT:")
    print(zip_path)
    print("Do not send anything under ~/.mxm_quant/ or .m6_capture_work/.")
