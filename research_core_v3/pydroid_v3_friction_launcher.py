"""One-button Android launcher for Research Core V3 maxT14 friction evidence."""
from __future__ import annotations

import tempfile
import zipfile
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path

from m6.ctrader_capture import CaptureContractError, READ_ONLY_SCOPE, redact_text, sha256_file
from m6.pydroid_oauth import PRIVATE_ROOT, ensure_v2_authorization
from research_core_v3.v3_friction_capture import (
    OUTPUT_REL,
    WORK_REL,
    V3MaxT14FrictionRunner,
    local_geometry_preflight,
)

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_PROTOBUF = "3.20.1"


def _require_versions() -> str:
    try:
        actual = package_version("protobuf")
    except PackageNotFoundError as exc:
        raise CaptureContractError(
            "missing protobuf 3.20.1; run V3_MAXT14_FRICTION_CAPTURE_RUN.py"
        ) from exc
    if actual != REQUIRED_PROTOBUF:
        raise CaptureContractError(
            f"protobuf {actual} incompatible; required {REQUIRED_PROTOBUF}"
        )
    return actual


def _probe(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    probe = path / ".mxm_v3_friction_write_probe"
    probe.write_text("MXM", encoding="utf-8")
    if probe.read_text(encoding="utf-8") != "MXM":
        raise CaptureContractError(f"directory is not writable: {path}")
    probe.unlink(missing_ok=True)


def local_preflight() -> dict:
    version = _require_versions()
    geometry = local_geometry_preflight(ROOT)
    _probe(ROOT / WORK_REL)
    _probe((ROOT / OUTPUT_REL).parent)
    _probe(PRIVATE_ROOT)
    with tempfile.TemporaryDirectory(prefix="mxm_v3_friction_preflight_") as td:
        path = Path(td) / "probe.zip"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("probe.txt", b"MXM")
        if len(sha256_file(path)) != 64:
            raise CaptureContractError("ZIP/SHA preflight failed")
    return {
        "protobuf": version,
        "scope": READ_ONLY_SCOPE,
        "symbols": geometry["symbols"],
        "exact_windows": geometry["exact_windows"],
        "transport_blocks": geometry["transport_blocks"],
        "base_bid_ask_requests_before_pagination": geometry[
            "base_bid_ask_requests_before_pagination"
        ],
        "overfetch_ratio_by_time": geometry["overfetch_ratio_by_time"],
        "network_connection_attempted": False,
        "credentials_used": False,
        "orders_permitted": False,
        "account_mutation_permitted": False,
        "protected_forward_opened": False,
    }


def main() -> None:
    print("MXM Research Core V3 — maxT14 authentic Pepperstone event-time friction capture")
    print("READ ONLY: accounts/view access | BID+ASK history | orders=NO | protected-forward=NO")
    print("Raw ticks stay local. Transfer ZIP contains exact-window quote evidence only.")

    try:
        report = local_preflight()
    except Exception as exc:
        print("[PREFLIGHT FAIL]", redact_text(str(exc)))
        raise SystemExit(2) from None

    print(
        "[PREFLIGHT PASS] "
        f"symbols={report['symbols']} | exact windows={report['exact_windows']} | "
        f"transport blocks={report['transport_blocks']} | "
        f"base BID/ASK requests={report['base_bid_ask_requests_before_pagination']}"
    )

    try:
        app, access_token, auth_mode = ensure_v2_authorization()
    except Exception as exc:
        print("[OAUTH BLOCKED SAFELY]", redact_text(str(exc)))
        raise SystemExit(1) from None
    print(f"[OAUTH] {auth_mode}; existing safe authorization is reused/refreshed when valid.")

    config = {"account_selection": "EXACT_ACCEPTED_FINGERPRINT_AUTOMATIC"}
    try:
        runner = V3MaxT14FrictionRunner(
            client_id=app["client_id"],
            client_secret=app["client_secret"],
            access_token=access_token,
            config=config,
            repo_root=ROOT,
        )
        zip_path = runner.run()
    except KeyboardInterrupt:
        print("\n[PAUSED] Hash-verified progress is resumable. Run this SAME file again.")
        raise SystemExit(130) from None
    except Exception as exc:
        print("\n[V3 FRICTION CAPTURE BLOCKED SAFELY]", redact_text(str(exc)))
        print("No order/account mutation/protected-forward opening occurred.")
        print("Rerun the SAME file to resume after the external issue is corrected.")
        raise SystemExit(1) from None
    finally:
        access_token = None

    print("\nCAPTURE COMPLETE.")
    print("Return ONLY this ZIP to ChatGPT:")
    print(zip_path)
    print("Keep the local .mxm_v3_maxt14_friction_work directory until evidence is accepted.")


if __name__ == "__main__":
    main()
