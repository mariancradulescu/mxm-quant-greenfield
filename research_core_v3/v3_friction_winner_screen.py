"""Winner-first broad authentic-friction screen for Research Core V3.

This is a discovery-prioritization screen, not a death certificate and not a
promotion gate. It prospectively samples all previously unmeasured gross-robust
symbol scopes, captures authentic Pepperstone BID/ASK history, and returns compact
derived spread diagnostics plus current safe symbol metadata. No raw ticks are
persisted or transferred. Protected-forward remains closed.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
import shutil
import statistics
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

from m6.cost_evidence import deterministic_zip_directory
from m6.ctrader_capture import CaptureContractError, atomic_write_json, sha256_file
from research_core_v3.v3_friction_capture import (
    ExactWindow,
    V3MaxT14FrictionRunner,
    _canonical,
    _sha_bytes,
)
from research_core_v3.v3_friction_staged import (
    HOUR_MS,
    StagedFrictionRunner,
    _dir_bytes,
    _load_gzip_json,
    build_reference_strata,
)

PLAN_REL = "research_core_v3/state/WINNER_FIRST_FRICTION_ACQUISITION_PLAN_V1.json"
DESIGN_REL = "research_core_v3/state/WINNER_FIRST_FRICTION_SCREEN_PLAN_V1.json"
WORK_REL = ".mxm_v3_winner_first_friction_work"
OUTPUT_REL = "v3_friction_winner_output/MXM_V3_WINNER_FIRST_FRICTION_SCREEN_EVIDENCE_V1"
TRANSFER_NAME = "MXM_V3_WINNER_FIRST_FRICTION_SCREEN_EVIDENCE_V1.zip"


def _rank(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(x) for x in parts).encode("utf-8")).hexdigest()


def _month_of_stratum(stratum: str) -> str:
    return str(stratum).split("|", 1)[0]


def freeze_winner_sampling(
    symbol: str,
    strata: Mapping[str, Mapping[int, tuple[ExactWindow, ...]]],
    *,
    seed: str,
    selected_strata_per_month: int,
    windows_per_hour: int,
) -> dict[str, Any]:
    if selected_strata_per_month <= 0 or windows_per_hour <= 0:
        raise CaptureContractError("winner-screen sampling counts must be positive")
    by_month: dict[str, list[str]] = defaultdict(list)
    for key in sorted(strata):
        by_month[_month_of_stratum(key)].append(key)

    selected: dict[str, Any] = {}
    for month in sorted(by_month):
        ordered_strata = sorted(
            by_month[month],
            key=lambda s: (_rank(seed, "STRATUM", symbol, month, s), s),
        )
        chosen_strata = ordered_strata[: min(selected_strata_per_month, len(ordered_strata))]
        for stratum in chosen_strata:
            hours = strata[stratum]
            ordered_hours = sorted(
                hours,
                key=lambda h: (_rank(seed, "HOUR", symbol, stratum, h), int(h)),
            )
            if not ordered_hours:
                continue
            hour = int(ordered_hours[0])
            ordered_windows = sorted(
                hours[hour],
                key=lambda w: (
                    _rank(seed, "WINDOW", symbol, stratum, hour, int(w.index)),
                    int(w.index),
                ),
            )
            chosen = ordered_windows[: min(windows_per_hour, len(ordered_windows))]
            selected[stratum] = {
                "month": month,
                "reference_strata_in_month": len(ordered_strata),
                "reference_hours_in_stratum": len(ordered_hours),
                "reference_windows_in_stratum": sum(len(hours[h]) for h in ordered_hours),
                "selected_hour_start_ms": hour,
                "reference_windows_in_selected_hour": len(hours[hour]),
                "selected_window_indices": [int(w.index) for w in chosen],
                "sampled_exact_windows": len(chosen),
            }
    return {
        "selected_strata": selected,
        "reference_nonempty_strata": len(strata),
        "reference_months": len(by_month),
        "selected_strata_count": len(selected),
        "sampled_exact_windows": sum(
            int(x["sampled_exact_windows"]) for x in selected.values()
        ),
    }


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    vals = sorted(float(x) for x in values)
    if len(vals) == 1:
        return vals[0]
    pos = max(0.0, min(1.0, float(q))) * (len(vals) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return vals[lo]
    weight = pos - lo
    return vals[lo] * (1.0 - weight) + vals[hi] * weight


def _spread_stats(rows: list[Mapping[str, Any]], delay: int) -> dict[str, Any]:
    key = f"d{int(delay)}s"
    values = [
        float(row[key]["spread_bps"])
        for row in rows
        if row.get(key, {}).get("fresh")
        and row.get(key, {}).get("spread_bps") is not None
    ]
    return {
        "fresh_count": len(values),
        "sampled_windows": len(rows),
        "fresh_fraction": (len(values) / len(rows)) if rows else 0.0,
        "min_spread_bps": min(values) if values else None,
        "p25_spread_bps": _quantile(values, 0.25),
        "median_spread_bps": statistics.median(values) if values else None,
        "mean_spread_bps": statistics.mean(values) if values else None,
        "max_spread_bps": max(values) if values else None,
    }


class WinnerFirstFrictionRunner(StagedFrictionRunner):
    def __init__(self, **kwargs):
        V3MaxT14FrictionRunner.__init__(self, **kwargs)
        design_rel = str(self.config.get("design_rel") or DESIGN_REL)
        self.design_path = self.repo_root / design_rel
        if not self.design_path.is_file():
            raise CaptureContractError(f"winner-first design missing: {design_rel}")
        self.design = json.loads(self.design_path.read_text(encoding="utf-8"))
        self._validate_winner_design()

        self.stage_work_dir = self.repo_root / str(
            self.config.get("stage_work_rel") or WORK_REL
        )
        self.stage_output_dir = self.repo_root / str(
            self.config.get("stage_output_rel") or OUTPUT_REL
        )
        transfer_name = str(
            self.config.get("stage_transfer_name") or TRANSFER_NAME
        )
        self.stage_bundle_path = self.stage_output_dir.parent / transfer_name
        self.stage_state_path = self.stage_work_dir / "state.json"
        self.hours_dir = self.stage_work_dir / "hours"
        self.stage_work_dir.mkdir(parents=True, exist_ok=True)
        self.hours_dir.mkdir(parents=True, exist_ok=True)
        self.stage_state = self._load_stage_state()
        self._peak_local_bytes = _dir_bytes(self.stage_work_dir)

    def _validate_winner_design(self) -> None:
        expected = self.design.get("binding_sha256")
        unsigned = dict(self.design)
        unsigned.pop("binding_sha256", None)
        if _sha_bytes(_canonical(unsigned)) != expected:
            raise CaptureContractError("winner-first design binding mismatch")
        if self.design.get("status") != "FROZEN_OUTCOME_BLIND_WINNER_FIRST_AUTHENTIC_FRICTION_SCREEN":
            raise CaptureContractError("winner-first design is not frozen")
        if self.design.get("source_plan_binding_sha256") != self.plan.get("binding_sha256"):
            raise CaptureContractError("winner-first design/source plan mismatch")
        scope = self.design["scope"]
        if int(scope["screen_symbols"]) != len(self.plan["targets"]):
            raise CaptureContractError("winner-first symbol count mismatch")
        if int(scope["screen_regions"]) != int(self.plan["selection"]["selected_regions"]):
            raise CaptureContractError("winner-first region count mismatch")
        if int(scope["full_reference_exact_windows"]) != sum(
            int(t["windows"]) for t in self.plan["targets"]
        ):
            raise CaptureContractError("winner-first reference-window count mismatch")
        if scope.get("protected_forward_opened") is not False:
            raise CaptureContractError("winner-first screen opens protected-forward")
        if int(scope.get("candidate_frozen_count", -1)) != 0:
            raise CaptureContractError("winner-first screen assumes frozen candidate")
        metrics = self.design["screen_metrics"]
        if metrics.get("no_promotion_from_screen") is not True:
            raise CaptureContractError("winner-first screen must forbid promotion")
        if metrics.get("no_candidate_freeze_from_screen") is not True:
            raise CaptureContractError("winner-first screen must forbid candidate freeze")
        sampling = self.design["sampling"]
        if int(sampling["fixed_transport_span_minutes"]) != 60:
            raise CaptureContractError("winner-first transport must stay frozen at 60m")
        if sampling.get("automatic_additional_acquisition") is not False:
            raise CaptureContractError("winner-first automatic additional acquisition forbidden")

    def _freeze_sampling(self) -> dict[str, Any]:
        seed = str(self.design["source_plan_binding_sha256"])
        policy = self.design["sampling"]
        sampling: dict[str, Any] = {}
        for target in self.plan["targets"]:
            symbol = str(target["symbol"])
            strata = build_reference_strata(self.scope_by_symbol[symbol])
            sampling[symbol] = freeze_winner_sampling(
                symbol,
                strata,
                seed=seed,
                selected_strata_per_month=int(
                    policy["selected_nonempty_session_strata_per_month"]
                ),
                windows_per_hour=int(policy["selected_exact_windows_per_hour"]),
            )
        freeze = {
            "schema": "mxm.research-core-v3.winner-first-sampling-freeze.v1",
            "design_binding_sha256": self.design["binding_sha256"],
            "source_plan_binding_sha256": self.plan["binding_sha256"],
            "sampling": sampling,
        }
        freeze["binding_sha256"] = _sha_bytes(_canonical(freeze))
        return freeze

    def _selected_windows(
        self,
        symbol: str,
        sampling_meta: Mapping[str, Any],
    ) -> list[tuple[str, int, tuple[ExactWindow, ...]]]:
        strata = build_reference_strata(self.scope_by_symbol[symbol])
        out = []
        for stratum, meta in sorted(sampling_meta["selected_strata"].items()):
            hour = int(meta["selected_hour_start_ms"])
            ids = {int(x) for x in meta["selected_window_indices"]}
            chosen = tuple(
                w for w in strata[stratum][hour] if int(w.index) in ids
            )
            if len(chosen) != len(ids):
                raise CaptureContractError("winner-first frozen window membership mismatch")
            out.append((stratum, hour, chosen))
        return out

    def _screen_summary(self) -> dict[str, Any]:
        symbols: dict[str, Any] = {}
        plausible = 0
        strong_negative = 0
        unresolved = 0
        for target in self.plan["targets"]:
            symbol = str(target["symbol"])
            rows: list[dict[str, Any]] = []
            files = sorted((self.hours_dir / symbol).glob("*.json.gz"))
            for path in files:
                rows.extend(_load_gzip_json(path)["rows"])
            delays = {
                str(delay): _spread_stats(rows, int(delay))
                for delay in self.design["sampling"]["delay_sensitivity_seconds"]
            }
            d0 = delays["0"]
            region_metrics = []
            for region in target["regions"]:
                gross = float(region["minimum_mean_response_bps"])
                def ratio(name: str) -> float | None:
                    value = d0.get(name)
                    return None if value is None else float(value) / gross
                if int(d0["fresh_count"]) >= 3 and d0["min_spread_bps"] is not None:
                    if float(d0["min_spread_bps"]) <= gross:
                        label = "FRICTION_PLAUSIBLE_SIGNAL"
                        plausible += 1
                    elif float(d0["min_spread_bps"]) > 2.0 * gross:
                        label = "STRONG_NEGATIVE_SIGNAL"
                        strong_negative += 1
                    else:
                        label = "UNRESOLVED_SCREEN"
                        unresolved += 1
                else:
                    label = "UNRESOLVED_SCREEN"
                    unresolved += 1
                region_metrics.append(
                    {
                        **dict(region),
                        "screen_label": label,
                        "min_spread_over_gross": ratio("min_spread_bps"),
                        "p25_spread_over_gross": ratio("p25_spread_bps"),
                        "median_spread_over_gross": ratio("median_spread_bps"),
                        "mean_spread_over_gross": ratio("mean_spread_bps"),
                        "screen_is_not_certification": True,
                    }
                )
            symbols[symbol] = {
                "symbol": symbol,
                "symbol_id": int(target["symbol_id"]),
                "representative_region_sha256": str(target["region_sha256"]),
                "sampled_hour_files": len(files),
                "delay_spread_metrics": delays,
                "regions": region_metrics,
            }
        return {
            "schema": "mxm.research-core-v3.winner-first-screen-summary.v1",
            "design_binding_sha256": self.design["binding_sha256"],
            "source_plan_binding_sha256": self.plan["binding_sha256"],
            "symbols": symbols,
            "region_label_counts": {
                "FRICTION_PLAUSIBLE_SIGNAL": plausible,
                "STRONG_NEGATIVE_SIGNAL": strong_negative,
                "UNRESOLVED_SCREEN": unresolved,
            },
            "candidate_frozen_count": 0,
            "net_certified_count": 0,
            "protected_forward_opened": False,
            "interpretation": (
                "Winner-first DEVELOPMENT screening only. Labels prioritize follow-up "
                "and cannot promote, freeze, or certify a candidate."
            ),
        }

    def _finalize(
        self,
        sampling_freeze: Mapping[str, Any],
        screen_summary: Mapping[str, Any],
        disk_start: Mapping[str, int],
    ) -> Path:
        if self.stage_output_dir.exists():
            shutil.rmtree(self.stage_output_dir)
        evidence = self.stage_output_dir / "evidence"
        derived = self.stage_output_dir / "derived"
        evidence.mkdir(parents=True, exist_ok=True)
        derived.mkdir(parents=True, exist_ok=True)

        atomic_write_json(evidence / "sampling_freeze.json", dict(sampling_freeze))
        atomic_write_json(evidence / "screen_summary.json", dict(screen_summary))
        atomic_write_json(
            evidence / "current_symbol_metadata.json",
            {
                "schema": "mxm.research-core-v3.current-symbol-metadata-screen.v1",
                "account_fingerprint_sha256": self.plan["broker_identity"][
                    "accepted_account_fingerprint_sha256"
                ],
                "current_only_not_historical_cost_truth": True,
                "symbols": self._symbol_evidence,
                "raw_account_id_embedded": False,
            },
        )

        for target in self.plan["targets"]:
            symbol = str(target["symbol"])
            files = sorted((self.hours_dir / symbol).glob("*.json.gz"))
            out = derived / f"{symbol}_WINNER_SCREEN_HOURS.jsonl.gz"
            with gzip.open(out, "wt", encoding="utf-8", compresslevel=9) as handle:
                for path in files:
                    doc = _load_gzip_json(path)
                    handle.write(
                        json.dumps(
                            doc,
                            sort_keys=True,
                            separators=(",", ":"),
                            ensure_ascii=False,
                        )
                        + "\n"
                    )

        disk_end = self._check_disk()
        manifest = {
            "schema": "mxm.research-core-v3.winner-first-friction-screen-evidence.v1",
            "design_binding_sha256": self.design["binding_sha256"],
            "source_plan_binding_sha256": self.plan["binding_sha256"],
            "account_fingerprint_sha256": self.plan["broker_identity"][
                "accepted_account_fingerprint_sha256"
            ],
            "screen_symbols": len(self.plan["targets"]),
            "screen_regions": int(self.plan["selection"]["selected_regions"]),
            "reference_exact_windows": int(
                self.plan["selection"]["selected_exact_quote_windows"]
            ),
            "protected_forward_opened": False,
            "candidate_frozen_count": 0,
            "net_certified_count": 0,
            "raw_ticks_embedded_in_transfer_bundle": False,
            "raw_tick_values_written_to_disk": False,
            "automatic_additional_acquisition": False,
            "screen_can_promote": False,
            "current_symbol_metadata_is_historical_cost_truth": False,
            "storage": {
                "stage_work_bytes_at_start": int(disk_start["stage_work_bytes"]),
                "stage_work_bytes_before_bundle": int(disk_end["stage_work_bytes"]),
                "peak_local_capture_bytes": int(self._peak_local_bytes),
                "hard_bundle_cap_bytes": int(
                    self.design["storage"]["hard_bundle_cap_bytes"]
                ),
            },
        }
        manifest["binding_sha256"] = _sha_bytes(_canonical(manifest))
        atomic_write_json(evidence / "manifest.json", manifest)

        checks = []
        for path in sorted(p for p in self.stage_output_dir.rglob("*") if p.is_file()):
            rel = path.relative_to(self.stage_output_dir).as_posix()
            checks.append(f"{sha256_file(path)}  {rel}")
        (self.stage_output_dir / "CHECKSUMS.sha256").write_text(
            "\n".join(checks) + "\n", encoding="utf-8"
        )

        bundle_sha = deterministic_zip_directory(
            self.stage_output_dir, self.stage_bundle_path
        )
        with zipfile.ZipFile(self.stage_bundle_path) as archive:
            bad = archive.testzip()
            if bad:
                raise CaptureContractError(
                    f"winner-first bundle ZIP CRC failed: {bad}"
                )
        bundle_bytes = self.stage_bundle_path.stat().st_size
        if bundle_bytes > int(self.design["storage"]["hard_bundle_cap_bytes"]):
            raise CaptureContractError("winner-first bundle exceeded hard cap")
        self._stage(
            f"[WINNER SCREEN COMPLETE] {self.stage_bundle_path.name} "
            f"sha256={bundle_sha} bytes={bundle_bytes}"
        )
        return self.stage_bundle_path

    def run_screen(self) -> Path:
        disk_start = self._check_disk()
        sampling_freeze = self._freeze_sampling()
        atomic_write_json(
            self.stage_work_dir / "sampling_freeze.json", sampling_freeze
        )
        account_id = self._authenticate_and_verify_targets()
        targets = {str(t["symbol"]): t for t in self.plan["targets"]}
        fixed_span = int(self.design["sampling"]["fixed_transport_span_minutes"])

        # No economic early stopping: complete every frozen symbol sample first.
        for symbol in sorted(targets):
            selected = self._selected_windows(
                symbol, sampling_freeze["sampling"][symbol]
            )
            for stratum, hour, windows in selected:
                self._stage(
                    f"[WINNER SCREEN] {symbol} {stratum} "
                    f"windows={len(windows)} transport={fixed_span}m"
                )
                self._capture_hour(
                    account_id,
                    targets[symbol],
                    hour,
                    windows,
                    fixed_span,
                )

        screen_summary = self._screen_summary()
        atomic_write_json(
            self.stage_work_dir / "screen_summary.json", screen_summary
        )
        return self._finalize(
            sampling_freeze, screen_summary, disk_start
        )


def winner_screen_geometry_preflight(
    repo_root: Path | str,
    *,
    plan_rel: str = PLAN_REL,
    design_rel: str = DESIGN_REL,
) -> dict[str, Any]:
    runner = object.__new__(WinnerFirstFrictionRunner)
    runner.repo_root = Path(repo_root)
    runner.config = {"expected_target_count": 56}
    runner.plan_path = runner.repo_root / plan_rel
    runner.plan = json.loads(runner.plan_path.read_text(encoding="utf-8"))
    runner._validate_plan()
    runner.scope_by_symbol = runner._load_scopes_and_blocks()
    runner.design_path = runner.repo_root / design_rel
    runner.design = json.loads(runner.design_path.read_text(encoding="utf-8"))
    runner._validate_winner_design()
    freeze = runner._freeze_sampling()

    hours = 0
    windows = 0
    per_symbol = {}
    for target in runner.plan["targets"]:
        symbol = str(target["symbol"])
        meta = freeze["sampling"][symbol]
        h = int(meta["selected_strata_count"])
        w = int(meta["sampled_exact_windows"])
        hours += h
        windows += w
        per_symbol[symbol] = {
            "sampled_hours": h,
            "sampled_exact_windows": w,
            "reference_months": int(meta["reference_months"]),
        }
    base_requests = 2 * hours
    baseline = self_rate = float(
        runner.design["prior_runtime_baseline"]["v8_stage1_api_attempts"]
    ) / float(
        runner.design["prior_runtime_baseline"]["v8_stage1_broker_call_elapsed_seconds"]
    )
    return {
        "schema": "mxm.research-core-v3.winner-first-geometry.v1",
        "design_binding_sha256": runner.design["binding_sha256"],
        "source_plan_binding_sha256": runner.plan["binding_sha256"],
        "screen_symbols": len(runner.plan["targets"]),
        "screen_regions": int(runner.plan["selection"]["selected_regions"]),
        "reference_exact_windows": int(
            runner.plan["selection"]["selected_exact_quote_windows"]
        ),
        "sampled_hours": hours,
        "sampled_exact_windows": windows,
        "base_bid_ask_requests_before_pagination": base_requests,
        "base_only_seconds_at_v8_stage1_rate": base_requests / baseline,
        "fixed_transport_span_minutes": int(
            runner.design["sampling"]["fixed_transport_span_minutes"]
        ),
        "stage0_benchmark_skipped": True,
        "automatic_additional_acquisition": False,
        "per_symbol": per_symbol,
    }
