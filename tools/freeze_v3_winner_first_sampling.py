#!/usr/bin/env python3
"""Generate the deterministic sparse winner-first sampling freeze.

Runs before Android acquisition. Reads only already-frozen DEVELOPMENT quote-window
scope membership; never calls the broker and never opens any economic response.
"""
from __future__ import annotations

import gzip
import json
import zipfile
from datetime import datetime
from pathlib import Path

from m6.ctrader_capture import CaptureContractError, atomic_write_json, sha256_file
from research_core_v3.v3_friction_capture import (
    _canonical,
    _sha_bytes,
    decode_delta_windows,
)
from research_core_v3.v3_friction_staged import build_reference_strata
from research_core_v3.v3_friction_winner_screen import (
    DESIGN_REL,
    PLAN_REL,
    SAMPLING_FREEZE_REL,
    freeze_winner_sampling,
)

ROOT = Path(__file__).resolve().parents[1]


def _validate_bound_document(doc: dict, name: str) -> None:
    expected = doc.get("binding_sha256")
    unsigned = dict(doc)
    unsigned.pop("binding_sha256", None)
    if _sha_bytes(_canonical(unsigned)) != expected:
        raise CaptureContractError(f"{name} binding mismatch")


def generate(target_path: Path | None = None) -> dict:
    state = ROOT / "research_core_v3" / "state"
    plan = json.loads((ROOT / PLAN_REL).read_text(encoding="utf-8"))
    design = json.loads((ROOT / DESIGN_REL).read_text(encoding="utf-8"))
    _validate_bound_document(plan, "winner-first plan")
    _validate_bound_document(design, "winner-first design")
    if design["source_plan_binding_sha256"] != plan["binding_sha256"]:
        raise CaptureContractError("winner-first plan/design binding mismatch")

    policy = design["sampling"]
    protected_ms = int(
        datetime.fromisoformat(
            plan["authority"]["protected_forward_start"].replace("Z", "+00:00")
        ).timestamp()
        * 1000
    )
    archives = {x["path"]: x for x in plan["scope_archives"]}
    verified_archives: set[str] = set()
    sampling = {}
    total_reference = 0
    total_hours = 0
    total_sampled_windows = 0

    for target in plan["targets"]:
        archive_name = target["archive"]
        archive_path = state / archive_name
        meta = archives.get(archive_name)
        if meta is None or not archive_path.is_file():
            raise CaptureContractError(
                f"winner-first scope archive missing: {archive_name}"
            )
        if archive_name not in verified_archives:
            if sha256_file(archive_path) != meta["sha256"]:
                raise CaptureContractError(
                    f"winner-first scope archive hash mismatch: {archive_name}"
                )
            verified_archives.add(archive_name)
        with zipfile.ZipFile(archive_path) as zf:
            blob = zf.read(target["shard"])
        if _sha_bytes(blob) != target["shard_sha256"]:
            raise CaptureContractError(
                f"{target['symbol']}: winner-first shard hash mismatch"
            )
        doc = json.loads(gzip.decompress(blob))
        if int(doc["symbol_id"]) != int(target["symbol_id"]):
            raise CaptureContractError(
                f"{target['symbol']}: winner-first symbol ID mismatch"
            )
        if str(doc["symbol"]) != str(target["symbol"]):
            raise CaptureContractError(
                f"{target['symbol']}: winner-first symbol name mismatch"
            )
        windows = decode_delta_windows(doc["quote_windows_delta_ms"])
        if len(windows) != int(target["windows"]):
            raise CaptureContractError(
                f"{target['symbol']}: winner-first reference count mismatch"
            )
        if any(int(end) >= protected_ms for _, end in windows):
            raise CaptureContractError(
                f"{target['symbol']}: winner-first reference reaches protected-forward"
            )

        strata = build_reference_strata({"windows": windows})
        frozen = freeze_winner_sampling(
            str(target["symbol"]),
            strata,
            seed=str(plan["binding_sha256"]),
            selected_strata_per_month=int(
                policy["selected_nonempty_session_strata_per_month"]
            ),
            windows_per_hour=int(
                policy["selected_exact_windows_per_hour"]
            ),
        )
        sampling[str(target["symbol"])] = frozen
        total_reference += len(windows)
        total_hours += int(frozen["selected_strata_count"])
        total_sampled_windows += int(frozen["sampled_exact_windows"])

    if total_reference != int(
        plan["selection"]["selected_exact_quote_windows"]
    ):
        raise CaptureContractError(
            "winner-first complete reference total mismatch"
        )
    if len(sampling) != int(plan["selection"]["selected_symbols"]):
        raise CaptureContractError(
            "winner-first frozen symbol count mismatch"
        )

    freeze = {
        "schema": "mxm.research-core-v3.winner-first-sampling-freeze.v1",
        "design_binding_sha256": design["binding_sha256"],
        "source_plan_binding_sha256": plan["binding_sha256"],
        "screen_symbols": len(sampling),
        "screen_regions": int(plan["selection"]["selected_regions"]),
        "reference_exact_windows": total_reference,
        "sampled_hours": total_hours,
        "sampled_exact_windows": total_sampled_windows,
        "sampling": sampling,
        "protected_forward_opened": False,
        "candidate_frozen_count": 0,
        "outcomes_used_for_membership": False,
    }
    freeze["binding_sha256"] = _sha_bytes(_canonical(freeze))
    destination = target_path or (ROOT / SAMPLING_FREEZE_REL)
    destination.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(destination, freeze)
    return freeze


def main() -> None:
    freeze = generate()
    path = ROOT / SAMPLING_FREEZE_REL
    print(
        "WINNER_SAMPLING_FREEZE",
        json.dumps(
            {
                "binding_sha256": freeze["binding_sha256"],
                "screen_symbols": freeze["screen_symbols"],
                "screen_regions": freeze["screen_regions"],
                "reference_exact_windows": freeze["reference_exact_windows"],
                "sampled_hours": freeze["sampled_hours"],
                "sampled_exact_windows": freeze["sampled_exact_windows"],
                "file_bytes": path.stat().st_size,
                "file_sha256": sha256_file(path),
            },
            sort_keys=True,
        ),
    )


if __name__ == "__main__":
    main()
