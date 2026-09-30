"""One-button Android launcher for Research Core V3 maxT14 friction evidence."""
from __future__ import annotations

import tempfile
import zipfile
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path

from m6.ctrader_capture import CaptureContractError, READ_ONLY_SCOPE, redact_text, sha256_file
from m6.pydroid_oauth import (
    PRIVATE_ROOT,
    choose_live_account_locally,
    ensure_v2_authorization,
    force_fresh_v2_authorization,
)
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


def _runner(app: dict, access_token: str) -> V3MaxT14FrictionRunner:
    return V3MaxT14FrictionRunner(
        client_id=app["client_id"],
        client_secret=app["client_secret"],
        access_token=access_token,
        config={"account_selection": "EXACT_ACCEPTED_FINGERPRINT_AUTOMATIC"},
        repo_root=ROOT,
    )


def _close_runner(runner) -> None:
    if runner is None:
        return
    try:
        runner.transport.close()
    except Exception:
        pass


def main() -> None:
    print("MXM Research Core V3 — account identity recovery + maxT14 friction capture")
    print("READ ONLY: accounts/view access | orders=NO | protected-forward=NO")
    print("NO historical BID/ASK request is sent until frozen account identity is unambiguous.")

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

    runner = None
    access_token = None
    try:
        app, access_token, auth_mode = ensure_v2_authorization()
        print(f"[OAUTH] {auth_mode}")
        runner = _runner(app, access_token)
        probe = runner.probe_account_identity(auth_mode)

        if probe["decision"] == "FORCE_FRESH_OAUTH":
            print(
                "[ACCOUNT RECOVERY] Saved/refreshable token does not authorize the "
                "frozen V3 account fingerprint."
            )
            print(
                "[ACCOUNT RECOVERY] Opening ONE fresh official cTrader authorization. "
                "Select the intended Pepperstone Europe LIVE research account. "
                "No historical quote request has started."
            )
            _close_runner(runner)
            runner = None
            access_token = None
            app, access_token, auth_mode = force_fresh_v2_authorization()
            print(f"[OAUTH] {auth_mode}")
            runner = _runner(app, access_token)
            probe = runner.probe_account_identity(auth_mode)

        if probe["decision"] == "MATCH_FROZEN_ACCOUNT":
            print(
                "[ACCOUNT IDENTITY PASS] Frozen Pepperstone LIVE fingerprint is uniquely "
                "authorized and all 14 exact symbol IDs/names are currently applicable."
            )
            print("[CAPTURE START AUTHORIZED] Identity ambiguity resolved before tick history.")
            zip_path = runner.run()
        elif probe["decision"] == "REBIND_REVIEW_REQUIRED":
            print(
                "[ACCOUNT RECOVERY] The frozen account fingerprint is still absent after "
                "fresh OAuth. No historical BID/ASK capture will start."
            )
            candidates = probe["authorized_live_accounts"]
            selected_id = choose_live_account_locally(candidates)
            proposal_path = runner.write_account_rebind_proposal(selected_id)
            print(
                "[ACCOUNT REBIND REVIEW REQUIRED] The locally selected account is verified "
                "Pepperstone LIVE and all 14 frozen symbol IDs/names are currently applicable."
            )
            print(
                "A scientifically eligible rebind proposal was created, but the frozen "
                "GitHub authority was NOT changed on this phone."
            )
            print("Return ONLY this JSON to ChatGPT:")
            print(proposal_path)
            print("Historical BID/ASK capture started: NO")
            raise SystemExit(3)
        else:
            raise CaptureContractError(
                f"account identity recovery failed closed: {probe['decision']}"
            )
    except KeyboardInterrupt:
        print("\n[PAUSED] No authority is silently changed. Existing verified progress is resumable.")
        raise SystemExit(130) from None
    except SystemExit:
        raise
    except Exception as exc:
        print("\n[V3 ACCOUNT/CAPTURE BLOCKED SAFELY]", redact_text(str(exc)))
        print("No order/account mutation/protected-forward opening occurred.")
        print("Do not substitute a different account or edit the frozen fingerprint manually.")
        raise SystemExit(1) from None
    finally:
        _close_runner(runner)
        access_token = None

    print("\nCAPTURE COMPLETE.")
    print("Return ONLY this ZIP to ChatGPT:")
    print(zip_path)
    print("Keep the local .mxm_v3_maxt14_friction_work directory until evidence is accepted.")


if __name__ == "__main__":
    main()
