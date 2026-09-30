"""Android launcher for staged Research Core V3 friction acquisition."""
from __future__ import annotations

import json
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
from research_core_v3.v3_friction_capture import local_geometry_preflight
from research_core_v3.v3_friction_staged import (
    DESIGN_REL,
    STAGE_WORK_REL,
    StagedFrictionRunner,
)

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_PROTOBUF = "3.20.1"


def _require_versions() -> str:
    try:
        actual = package_version("protobuf")
    except PackageNotFoundError as exc:
        raise CaptureContractError(
            "missing protobuf 3.20.1; run V3_MAXT14_FRICTION_STAGE_RUN.py"
        ) from exc
    if actual != REQUIRED_PROTOBUF:
        raise CaptureContractError(
            f"protobuf {actual} incompatible; required {REQUIRED_PROTOBUF}"
        )
    return actual


def _probe(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    probe = path / ".mxm_v3_staged_write_probe"
    probe.write_text("MXM", encoding="utf-8")
    if probe.read_text(encoding="utf-8") != "MXM":
        raise CaptureContractError(f"directory is not writable: {path}")
    probe.unlink(missing_ok=True)


def local_preflight() -> dict:
    version = _require_versions()
    geometry = local_geometry_preflight(ROOT)
    design = json.loads((ROOT / DESIGN_REL).read_text(encoding="utf-8"))
    _probe(ROOT / STAGE_WORK_REL)
    _probe(PRIVATE_ROOT)
    with tempfile.TemporaryDirectory(prefix="mxm_v3_staged_preflight_") as td:
        path = Path(td) / "probe.zip"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("probe.txt", b"MXM")
        if len(sha256_file(path)) != 64:
            raise CaptureContractError("ZIP/SHA preflight failed")
    return {
        "protobuf": version,
        "scope": READ_ONLY_SCOPE,
        "symbols": geometry["symbols"],
        "reference_exact_windows": geometry["exact_windows"],
        "stage0_base_probes": int(design["stage0_benchmark"]["planned_base_probes"]),
        "stage_hours_per_stratum": list(
            design["stage1_sampling"]["stage_hours_per_nonempty_stratum"]
        ),
        "raw_ticks_written_to_disk": False,
        "disk_hard_cap_bytes": int(design["storage"]["stage_work_dir_hard_cap_bytes"]),
        "protected_forward_opened": False,
        "orders_permitted": False,
    }


def _runner(app: dict, access_token: str) -> StagedFrictionRunner:
    return StagedFrictionRunner(
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
    print("MXM Research Core V3 — STAGED authentic friction acquisition")
    print("Stage 0: transport benchmark only | Stage 1: outcome-blind sequential sample")
    print("READ ONLY | orders=NO | protected-forward=NO | raw ticks on disk=NO")
    try:
        report = local_preflight()
    except Exception as exc:
        print("[PREFLIGHT FAIL]", redact_text(str(exc)))
        raise SystemExit(2) from None

    print(
        "[PREFLIGHT PASS] "
        f"symbols={report['symbols']} | reference windows={report['reference_exact_windows']} | "
        f"stage0 probes={report['stage0_base_probes']} | "
        f"stage looks={report['stage_hours_per_stratum']} hours/stratum | "
        f"disk hard cap={report['disk_hard_cap_bytes']/1024/1024:.0f}MiB"
    )

    runner = None
    access_token = None
    try:
        app, access_token, auth_mode = ensure_v2_authorization()
        print(f"[OAUTH] {auth_mode}")
        runner = _runner(app, access_token)
        probe = runner.probe_account_identity(auth_mode)

        if probe["decision"] == "FORCE_FRESH_OAUTH":
            print("[ACCOUNT] saved token does not authorize the accepted rebound fingerprint")
            print("[ACCOUNT] opening ONE fresh official cTrader authorization")
            _close_runner(runner)
            runner = None
            access_token = None
            app, access_token, auth_mode = force_fresh_v2_authorization()
            print(f"[OAUTH] {auth_mode}")
            runner = _runner(app, access_token)
            probe = runner.probe_account_identity(auth_mode)

        if probe["decision"] == "MATCH_FROZEN_ACCOUNT":
            print("[ACCOUNT PASS] accepted Pepperstone LIVE identity and 14 symbols verified")
            bundle = runner.run_staged()
        elif probe["decision"] == "REBIND_REVIEW_REQUIRED":
            print("[ACCOUNT BLOCK] accepted rebound fingerprint is absent after fresh OAuth")
            candidates = probe["authorized_live_accounts"]
            selected_id = choose_live_account_locally(candidates)
            proposal = runner.write_account_rebind_proposal(selected_id)
            print("No historical staged acquisition started.")
            print("Return ONLY this JSON to ChatGPT:")
            print(proposal)
            raise SystemExit(3)
        else:
            raise CaptureContractError(
                f"staged account identity failed closed: {probe['decision']}"
            )
    except KeyboardInterrupt:
        print("\n[PAUSED] completed staged-hour evidence remains resumable.")
        raise SystemExit(130) from None
    except SystemExit:
        raise
    except Exception as exc:
        print("\n[STAGED CAPTURE BLOCKED SAFELY]", redact_text(str(exc)))
        print("No order/account mutation/protected-forward opening occurred.")
        raise SystemExit(1) from None
    finally:
        _close_runner(runner)
        access_token = None

    print("\nSTAGED ACQUISITION COMPLETE.")
    print("Return ONLY this ZIP to ChatGPT:")
    print(bundle)
    print("Do not run the old exhaustive V5 capture.")


if __name__ == "__main__":
    main()
