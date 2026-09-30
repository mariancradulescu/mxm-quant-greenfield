"""Android launcher for Research Core V3 winner-first friction screen."""
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
from research_core_v3.v3_friction_winner_screen import (
    DESIGN_REL,
    OUTPUT_REL,
    PLAN_REL,
    SAMPLING_FREEZE_REL,
    TRANSFER_NAME,
    WORK_REL,
    WinnerFirstFrictionRunner,
    winner_screen_geometry_preflight,
)

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_PROTOBUF = "3.20.1"
BASE_WORK_REL = ".mxm_v3_winner_first_base_work"


def _require_versions() -> str:
    try:
        actual = package_version("protobuf")
    except PackageNotFoundError as exc:
        raise CaptureContractError(
            "missing protobuf 3.20.1; run V3_WINNER_FIRST_FRICTION_SCREEN_RUN.py"
        ) from exc
    if actual != REQUIRED_PROTOBUF:
        raise CaptureContractError(
            f"protobuf {actual} incompatible; required {REQUIRED_PROTOBUF}"
        )
    return actual


def _probe(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    probe = path / ".mxm_v3_winner_write_probe"
    probe.write_text("MXM", encoding="utf-8")
    if probe.read_text(encoding="utf-8") != "MXM":
        raise CaptureContractError(f"directory is not writable: {path}")
    probe.unlink(missing_ok=True)


def local_preflight() -> dict:
    version = _require_versions()
    geometry = winner_screen_geometry_preflight(ROOT)
    _probe(ROOT / WORK_REL)
    _probe(ROOT / BASE_WORK_REL)
    _probe(PRIVATE_ROOT)
    with tempfile.TemporaryDirectory(prefix="mxm_v3_winner_preflight_") as td:
        path = Path(td) / "probe.zip"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("probe.txt", b"MXM")
        if len(sha256_file(path)) != 64:
            raise CaptureContractError("ZIP/SHA preflight failed")
    return {
        "protobuf": version,
        "scope": READ_ONLY_SCOPE,
        **geometry,
        "raw_ticks_written_to_disk": False,
        "protected_forward_opened": False,
        "orders_permitted": False,
    }


def _runner(app: dict, access_token: str) -> WinnerFirstFrictionRunner:
    return WinnerFirstFrictionRunner(
        client_id=app["client_id"],
        client_secret=app["client_secret"],
        access_token=access_token,
        config={
            "account_selection": "EXACT_ACCEPTED_FINGERPRINT_AUTOMATIC",
            "expected_target_count": 56,
            "plan_rel": PLAN_REL,
            "design_rel": DESIGN_REL,
            "sampling_freeze_rel": SAMPLING_FREEZE_REL,
            "base_work_rel": BASE_WORK_REL,
            "base_output_rel": "v3_winner_base_output/unused",
            "base_transfer_name": "UNUSED_WINNER_BASE.zip",
            "stage_work_rel": WORK_REL,
            "stage_output_rel": OUTPUT_REL,
            "stage_transfer_name": TRANSFER_NAME,
        },
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
    print("MXM Research Core V3 — WINNER-FIRST authentic friction screen V9")
    print("56 unmeasured symbols | 57 gross regions | one sparse global screen")
    print("READ ONLY | orders=NO | protected-forward=NO | raw ticks on disk=NO")
    print("SCREEN ONLY | candidate freeze=NO | net certification=NO")
    try:
        report = local_preflight()
    except Exception as exc:
        print("[PREFLIGHT FAIL]", redact_text(str(exc)))
        raise SystemExit(2) from None

    print(
        "[PREFLIGHT PASS] "
        f"symbols={report['screen_symbols']} | regions={report['screen_regions']} | "
        f"reference_windows={report['reference_exact_windows']} | "
        f"sampled_hours={report['sampled_hours']} | "
        f"sampled_windows={report['sampled_exact_windows']} | "
        f"base_requests={report['base_bid_ask_requests_before_pagination']} | "
        f"V8-rate base time={report['base_only_seconds_at_v8_stage1_rate']/60:.1f}min"
    )

    runner = None
    access_token = None
    try:
        app, access_token, auth_mode = ensure_v2_authorization()
        print(f"[OAUTH] {auth_mode}")
        runner = _runner(app, access_token)
        probe = runner.probe_account_identity(auth_mode)

        if probe["decision"] == "FORCE_FRESH_OAUTH":
            print("[ACCOUNT] saved token does not authorize the accepted account")
            print("[ACCOUNT] opening ONE fresh official cTrader authorization")
            _close_runner(runner)
            runner = None
            access_token = None
            app, access_token, auth_mode = force_fresh_v2_authorization()
            print(f"[OAUTH] {auth_mode}")
            runner = _runner(app, access_token)
            probe = runner.probe_account_identity(auth_mode)

        if probe["decision"] == "MATCH_FROZEN_ACCOUNT":
            print(
                "[ACCOUNT PASS] accepted Pepperstone LIVE identity and "
                f"{probe['verified_symbol_count']} winner-screen symbols verified"
            )
            bundle = runner.run_screen()
        elif probe["decision"] == "REBIND_REVIEW_REQUIRED":
            print("[ACCOUNT BLOCK] accepted fingerprint absent after fresh OAuth")
            selected_id = choose_live_account_locally(
                probe["authorized_live_accounts"]
            )
            proposal = runner.write_account_rebind_proposal(selected_id)
            print("No winner-first market-history screen started.")
            print("Return ONLY this JSON to ChatGPT:")
            print(proposal)
            raise SystemExit(3)
        else:
            raise CaptureContractError(
                f"winner-first account identity failed closed: {probe['decision']}"
            )
    except KeyboardInterrupt:
        print("\n[PAUSED] completed sparse evidence remains resumable.")
        raise SystemExit(130) from None
    except SystemExit:
        raise
    except Exception as exc:
        print("\n[WINNER SCREEN BLOCKED SAFELY]", redact_text(str(exc)))
        print("No order/account mutation/protected-forward opening occurred.")
        raise SystemExit(1) from None
    finally:
        _close_runner(runner)
        access_token = None

    print("\nWINNER-FIRST FRICTION SCREEN COMPLETE.")
    print("Android acquisition is STOPPED. Do not start another look.")
    print("Return ONLY this ZIP to ChatGPT:")
    print(bundle)


if __name__ == "__main__":
    main()
