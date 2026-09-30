"""Fast global authentic-friction triage for Research Core V3.

This V7 successor preserves the frozen V6 science but replaces automatic per-symbol
multi-look execution with one prospectively frozen, globally comparable campaign.
All 14 priority regions complete their first triage sample before any economic
classification is made. No second look is requested automatically.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
import shutil
import time
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

from m6.cost_evidence import BoundaryQuoteIndex, atomic_write_bytes, deterministic_zip_directory
from m6.ctrader_capture import CaptureContractError, atomic_write_json, sha256_file
from research_core_v3.v3_friction_capture import ExactWindow, V3MaxT14FrictionRunner, _canonical, _sha_bytes
from research_core_v3.v3_friction_staged import (
    HOUR_MS,
    StagedFrictionRunner,
    _dir_bytes,
    _gzip_json_bytes,
    _load_gzip_json,
    benchmark_anchor_hours,
    build_reference_strata,
)

DESIGN_REL = "research_core_v3/state/GLOBAL_FRICTION_TRIAGE_PLAN_V1.json"
WORK_REL = ".mxm_v3_global_friction_triage_work"
OUTPUT_REL = "v3_friction_triage_output/MXM_V3_GLOBAL_FRICTION_TRIAGE_EVIDENCE_V1"
TRANSFER_NAME = "MXM_V3_GLOBAL_FRICTION_TRIAGE_EVIDENCE_V1.zip"


def _hour_hash(seed: str, symbol: str, stratum: str, hour_start: int) -> str:
    return hashlib.sha256(
        f"{seed}|HOUR|{symbol}|{stratum}|{hour_start}".encode("utf-8")
    ).hexdigest()


def _window_hash(
    seed: str,
    symbol: str,
    stratum: str,
    hour_start: int,
    window_index: int,
) -> str:
    return hashlib.sha256(
        (
            f"{seed}|WINDOW|{symbol}|{stratum}|{hour_start}|"
            f"{window_index}"
        ).encode("utf-8")
    ).hexdigest()


def freeze_global_triage_sampling(
    symbol: str,
    strata: Mapping[str, Mapping[int, tuple[ExactWindow, ...]]],
    *,
    seed: str,
    hours_per_stratum: int,
    windows_per_hour: int,
) -> dict[str, Any]:
    if hours_per_stratum != 1:
        raise CaptureContractError("V7 initial triage requires exactly one hour per stratum")
    if windows_per_hour <= 0:
        raise CaptureContractError("V7 windows_per_hour must be positive")
    out: dict[str, Any] = {}
    for stratum in sorted(strata):
        hours = strata[stratum]
        ordered_hours = sorted(
            hours, key=lambda h: (_hour_hash(seed, symbol, stratum, h), h)
        )
        selected_hours = ordered_hours[: min(hours_per_stratum, len(ordered_hours))]
        chosen_by_hour: dict[str, list[int]] = {}
        reference_count_by_hour: dict[str, int] = {}
        sampled_exact_windows = 0
        max_reference_windows = max((len(hours[h]) for h in ordered_hours), default=0)
        for hour in selected_hours:
            ordered_windows = sorted(
                hours[hour],
                key=lambda w: (
                    _window_hash(seed, symbol, stratum, hour, int(w.index)),
                    int(w.index),
                ),
            )
            chosen = [
                int(w.index)
                for w in ordered_windows[: min(windows_per_hour, len(ordered_windows))]
            ]
            chosen_by_hour[str(int(hour))] = chosen
            reference_count_by_hour[str(int(hour))] = len(hours[hour])
            sampled_exact_windows += len(chosen)
        out[stratum] = {
            "reference_hours": len(ordered_hours),
            "reference_windows": sum(len(hours[h]) for h in ordered_hours),
            "max_windows_per_hour": max_reference_windows,
            "proxy_max_windows_per_hour": min(windows_per_hour, max_reference_windows),
            "selected_hour_start_ms": [int(h) for h in selected_hours],
            "selected_window_indices_by_hour": chosen_by_hour,
            "reference_window_count_by_selected_hour": reference_count_by_hour,
            "sampled_exact_windows": sampled_exact_windows,
        }
    return out


def global_death_bound(
    *,
    gross_bps: float,
    total_reference_windows: int,
    strata_meta: Mapping[str, Mapping[str, Any]],
    sampled_cluster_totals: Mapping[str, list[float]],
    alpha: float,
) -> dict[str, float]:
    gross = float(gross_bps)
    total_windows = int(total_reference_windows)
    if gross <= 0 or total_windows <= 0 or not (0 < alpha < 1):
        raise CaptureContractError("invalid global death-bound inputs")
    estimate = 0.0
    range_sq = 0.0
    used = 0
    for stratum, totals in sampled_cluster_totals.items():
        meta = strata_meta[stratum]
        population_hours = int(meta["reference_hours"])
        proxy_max_windows = int(meta["proxy_max_windows_per_hour"])
        sample_hours = len(totals)
        if population_hours <= 0 or sample_hours <= 0:
            continue
        if sample_hours > population_hours:
            raise CaptureContractError("sampled more hours than reference population")
        coeff = population_hours / (total_windows * sample_hours)
        estimate += coeff * sum(float(x) for x in totals)
        cluster_range = proxy_max_windows * (2.0 * gross)
        range_sq += sample_hours * (coeff * cluster_range) ** 2
        used += sample_hours
    if used == 0:
        return {
            "estimate_clipped_proxy_bps": 0.0,
            "half_width_bps": float("inf"),
            "lower_bound_bps": 0.0,
        }
    width = math.sqrt(0.5 * math.log(1.0 / alpha) * range_sq)
    return {
        "estimate_clipped_proxy_bps": estimate,
        "half_width_bps": width,
        "lower_bound_bps": max(0.0, estimate - width),
    }


class GlobalFrictionTriageRunner(StagedFrictionRunner):
    def __init__(self, **kwargs):
        V3MaxT14FrictionRunner.__init__(self, **kwargs)
        self.design_path = self.repo_root / DESIGN_REL
        if not self.design_path.is_file():
            raise CaptureContractError("global friction triage design missing")
        self.design = json.loads(self.design_path.read_text(encoding="utf-8"))
        self._validate_global_design()
        self.stage_work_dir = self.repo_root / WORK_REL
        self.stage_output_dir = self.repo_root / OUTPUT_REL
        self.stage_bundle_path = self.stage_output_dir.parent / TRANSFER_NAME
        self.stage_state_path = self.stage_work_dir / "state.json"
        self.hours_dir = self.stage_work_dir / "hours"
        self.stage_work_dir.mkdir(parents=True, exist_ok=True)
        self.hours_dir.mkdir(parents=True, exist_ok=True)
        self.stage_state = self._load_global_state()
        self._peak_local_bytes = self._aggregate_local_bytes()

    def _validate_global_design(self) -> None:
        expected = self.design.get("binding_sha256")
        unsigned = dict(self.design)
        unsigned.pop("binding_sha256", None)
        if _sha_bytes(_canonical(unsigned)) != expected:
            raise CaptureContractError("global triage design binding mismatch")
        if self.design.get("status") != "FROZEN_OUTCOME_BLIND_GLOBAL_AUTHENTIC_FRICTION_TRIAGE":
            raise CaptureContractError("global triage design is not frozen")
        if self.design.get("source_plan_binding_sha256") != self.plan.get("binding_sha256"):
            raise CaptureContractError("global triage/source plan mismatch")
        scope = self.design["scope"]
        if int(scope["full_reference_exact_windows"]) != 691_919:
            raise CaptureContractError("global triage reference-window count changed")
        if scope.get("protected_forward_opened") is not False:
            raise CaptureContractError("global triage opens protected-forward")
        if int(scope.get("candidate_frozen_count", -1)) != 0:
            raise CaptureContractError("global triage assumes frozen candidate")
        triage = self.design["initial_global_triage"]
        if int(triage.get("campaign_looks", 0)) != 1:
            raise CaptureContractError("V7 initial campaign must contain exactly one look")
        if triage.get("automatic_additional_acquisition") is not False:
            raise CaptureContractError("automatic additional acquisition is forbidden")

    def _load_global_state(self) -> dict[str, Any]:
        contract = {
            "schema": "mxm.research-core-v3.global-friction-triage-resume.v1",
            "design_binding_sha256": self.design["binding_sha256"],
            "source_plan_binding_sha256": self.plan["binding_sha256"],
            "accepted_account_fingerprint_sha256": self.plan["broker_identity"][
                "accepted_account_fingerprint_sha256"
            ],
        }
        contract["binding_sha256"] = _sha_bytes(_canonical(contract))
        if self.stage_state_path.is_file():
            try:
                state = json.loads(self.stage_state_path.read_text(encoding="utf-8"))
            except Exception:
                state = None
            if isinstance(state, dict) and state.get("contract") == contract:
                return state
        state = {
            "schema": "mxm.research-core-v3.global-friction-triage-resume-state.v1",
            "contract": contract,
            "completed_hours": {},
        }
        atomic_write_json(self.stage_state_path, state)
        return state

    def _aggregate_local_bytes(self) -> int:
        total = _dir_bytes(self.stage_work_dir)
        total += _dir_bytes(self.stage_output_dir)
        if self.stage_bundle_path.is_file():
            total += self.stage_bundle_path.stat().st_size
        return int(total)

    def _check_global_disk(self) -> dict[str, int]:
        usage = shutil.disk_usage(self.repo_root)
        work = _dir_bytes(self.stage_work_dir)
        output = _dir_bytes(self.stage_output_dir)
        bundle = self.stage_bundle_path.stat().st_size if self.stage_bundle_path.is_file() else 0
        aggregate = int(work + output + bundle)
        self._peak_local_bytes = max(self._peak_local_bytes, aggregate)
        storage = self.design["storage"]
        if usage.free < int(storage["minimum_free_disk_bytes"]):
            raise CaptureContractError("free disk below global triage safety floor")
        if aggregate > int(storage["aggregate_local_capture_artifacts_hard_cap_bytes"]):
            raise CaptureContractError("global triage local artifact hard cap exceeded")
        return {
            "free_bytes": int(usage.free),
            "stage_work_bytes": int(work),
            "stage_output_bytes": int(output),
            "bundle_bytes": int(bundle),
            "aggregate_capture_bytes": aggregate,
        }

    def _reference(self) -> tuple[dict[str, Any], dict[str, Any]]:
        triage = self.design["initial_global_triage"]
        seed = str(self.design["source_plan_binding_sha256"])
        sampling: dict[str, Any] = {}
        anchors: dict[str, Any] = {}
        for target in self.plan["targets"]:
            symbol = str(target["symbol"])
            strata = build_reference_strata(self.scope_by_symbol[symbol])
            sampling[symbol] = freeze_global_triage_sampling(
                symbol,
                strata,
                seed=seed,
                hours_per_stratum=int(triage["sample_hours_per_nonempty_stratum"]),
                windows_per_hour=int(triage["max_frozen_exact_windows_per_sampled_hour"]),
            )
            anchors[symbol] = benchmark_anchor_hours(strata)
        freeze = {
            "schema": "mxm.research-core-v3.global-friction-triage-sampling-freeze.v1",
            "design_binding_sha256": self.design["binding_sha256"],
            "source_plan_binding_sha256": self.plan["binding_sha256"],
            "sampling": sampling,
        }
        freeze["binding_sha256"] = _sha_bytes(_canonical(freeze))
        benchmark = {
            "schema": "mxm.research-core-v3.global-friction-triage-benchmark-freeze.v1",
            "design_binding_sha256": self.design["binding_sha256"],
            "anchors_by_symbol": anchors,
            "probe_spans_minutes": list(self.design["stage0_benchmark"]["probe_spans_minutes"]),
        }
        benchmark["binding_sha256"] = _sha_bytes(_canonical(benchmark))
        return freeze, benchmark

    def _run_stage0(
        self, account_id: int, benchmark_freeze: Mapping[str, Any]
    ) -> tuple[dict[str, Any], dict[str, int]]:
        self._stage("[STAGE 0] measured transport benchmark; no spreads persisted")
        records: list[dict[str, Any]] = []
        spans = [int(x) for x in self.design["stage0_benchmark"]["probe_spans_minutes"]]
        targets = {str(t["symbol"]): t for t in self.plan["targets"]}
        protected_ms = int(
            __import__("datetime").datetime.fromisoformat(
                self.plan["authority"]["protected_forward_start"].replace("Z", "+00:00")
            ).timestamp()
            * 1000
        )
        for symbol in sorted(benchmark_freeze["anchors_by_symbol"]):
            target = targets[symbol]
            reference_windows = self.scope_by_symbol[symbol]["windows"]
            development_min_ms = min(int(x[0]) for x in reference_windows)
            development_max_ms = max(int(x[1]) for x in reference_windows)
            for anchor_hour in benchmark_freeze["anchors_by_symbol"][symbol]:
                center = int(anchor_hour) + HOUR_MS // 2
                for span_min in spans:
                    span_ms = span_min * 60_000
                    start_ms = max(development_min_ms, center - span_ms // 2)
                    end_ms = min(development_max_ms, protected_ms - 1, center + span_ms // 2)
                    if end_ms <= start_ms:
                        raise CaptureContractError("stage0 benchmark escaped DEVELOPMENT")
                    useful = sum(
                        1
                        for start, end in reference_windows
                        if int(start) <= end_ms and int(end) >= start_ms
                    )
                    for side in ("BID", "ASK"):
                        _, meta = self._probe_range(
                            account_id, target, side, start_ms, end_ms, keep_ticks=False
                        )
                        meta.update(
                            {
                                "symbol": symbol,
                                "symbol_id": int(target["symbol_id"]),
                                "anchor_hour_start_ms": int(anchor_hour),
                                "probe_span_minutes": int(span_min),
                                "reference_windows_in_probe": int(useful),
                            }
                        )
                        records.append(meta)
                        self._check_global_disk()

        eligible = [int(x) for x in self.design["stage0_benchmark"]["stage1_eligible_spans_minutes"]]
        profile: dict[str, int] = {}
        profile_metrics: dict[str, Any] = {}
        for symbol in sorted(targets):
            scored: list[tuple[tuple[float, float, float, int], int, dict[str, float]]] = []
            for candidate in eligible:
                subset = [
                    r for r in records
                    if r["symbol"] == symbol and int(r["probe_span_minutes"]) == candidate
                ]
                if not subset or any(r["broker_history_unavailable"] for r in subset):
                    continue
                useful = sum(max(0, int(r["reference_windows_in_probe"])) for r in subset)
                if useful <= 0:
                    continue
                elapsed = sum(max(1, int(r["elapsed_ms"])) for r in subset)
                response_bytes = sum(int(r["protobuf_response_bytes"]) for r in subset)
                attempts = sum(int(r["api_attempts"]) for r in subset)
                metrics = {
                    "elapsed_ms_per_reference_window": elapsed / useful,
                    "protobuf_bytes_per_reference_window": response_bytes / useful,
                    "api_attempts_per_reference_window": attempts / useful,
                }
                score = (
                    metrics["elapsed_ms_per_reference_window"],
                    metrics["protobuf_bytes_per_reference_window"],
                    metrics["api_attempts_per_reference_window"],
                    candidate,
                )
                scored.append((score, candidate, metrics))
            if not scored:
                chosen = min(eligible)
                profile_metrics[symbol] = {
                    "selected_span_minutes": chosen,
                    "fallback": True,
                    "reason": "NO_CLEAN_BENCHMARK_CANDIDATE",
                }
            else:
                scored.sort(key=lambda x: x[0])
                _, chosen, metrics = scored[0]
                profile_metrics[symbol] = {
                    "selected_span_minutes": chosen,
                    "fallback": False,
                    **metrics,
                }
            profile[symbol] = int(chosen)

        disk = self._check_global_disk()
        report = {
            "schema": "mxm.research-core-v3.global-friction-triage-transport-benchmark.v1",
            "design_binding_sha256": self.design["binding_sha256"],
            "benchmark_freeze_binding_sha256": benchmark_freeze["binding_sha256"],
            "economic_values_recorded": False,
            "raw_tick_values_persisted": False,
            "records": records,
            "summary": {
                "planned_base_probes": int(self.design["stage0_benchmark"]["planned_base_probes"]),
                "actual_probe_records": len(records),
                "successful_api_responses": sum(r["successful_api_responses"] for r in records),
                "api_attempts": sum(r["api_attempts"] for r in records),
                "ticks_returned": sum(r["tick_count"] for r in records),
                "protobuf_response_bytes": sum(r["protobuf_response_bytes"] for r in records),
                "has_more_count": sum(r["has_more_count"] for r in records),
                "transport_retry_count": sum(r["transport_retry_count"] for r in records),
                "broker_history_unavailable_events": sum(
                    len(r["broker_history_unavailable"]) for r in records
                ),
                "aggregate_capture_bytes_after_benchmark": disk["aggregate_capture_bytes"],
            },
            "recommended_transport_span_minutes_by_symbol": profile,
            "transport_selection_metrics_by_symbol": profile_metrics,
            "broader_180m_probe_evaluated": True,
            "broader_180m_stage1_eligible": False,
        }
        report["binding_sha256"] = _sha_bytes(_canonical(report))
        return report, profile

    def _capture_triage_hour(
        self,
        account_id: int,
        target: Mapping[str, Any],
        hour_start: int,
        windows: tuple[ExactWindow, ...],
        span_min: int,
        *,
        reference_window_count: int,
    ) -> dict[str, Any]:
        symbol = str(target["symbol"])
        path = self._hour_file(symbol, hour_start)
        key = f"{symbol}|{hour_start}"
        saved = self.stage_state["completed_hours"].get(key)
        if isinstance(saved, dict) and path.is_file() and sha256_file(path) == saved.get("sha256"):
            return _load_gzip_json(path)
        triage = self.design["initial_global_triage"]
        delays = [int(x) for x in triage["delay_sensitivity_seconds"]]
        age_limit_ms = int(triage["fresh_quote_age_limit_seconds"]) * 1000
        rows: list[dict[str, Any]] = []
        provenance: list[dict[str, Any]] = []
        for start_ms, end_ms, block_windows in self._split_windows(hour_start, windows, span_min):
            bids, bid_meta = self._probe_range(
                account_id, target, "BID", start_ms, end_ms, keep_ticks=True
            )
            asks, ask_meta = self._probe_range(
                account_id, target, "ASK", start_ms, end_ms, keep_ticks=True
            )
            index = BoundaryQuoteIndex(bids, asks)
            provenance.append(
                {"from_ms": start_ms, "to_ms": end_ms, "bid": bid_meta, "ask": ask_meta}
            )
            for window in block_windows:
                row = {
                    "exact_window_index": int(window.index),
                    "window_start_ms": int(window.start_ms),
                    "boundary_ms": int(window.boundary_ms),
                    "window_end_ms": int(window.end_ms),
                }
                for delay in delays:
                    checkpoint = window.boundary_ms + delay * 1000
                    state = index.causal_state_at_boundary(checkpoint)
                    bid_ok = state.bid_timestamp_ms is not None and state.bid_timestamp_ms >= window.start_ms
                    ask_ok = state.ask_timestamp_ms is not None and state.ask_timestamp_ms >= window.start_ms
                    bid = state.bid if bid_ok else None
                    ask = state.ask if ask_ok else None
                    bid_ts = state.bid_timestamp_ms if bid_ok else None
                    ask_ts = state.ask_timestamp_ms if ask_ok else None
                    bid_age = None if bid_ts is None else checkpoint - bid_ts
                    ask_age = None if ask_ts is None else checkpoint - ask_ts
                    fresh = (
                        bid is not None
                        and ask is not None
                        and bid_age is not None
                        and ask_age is not None
                        and max(bid_age, ask_age) <= age_limit_ms
                    )
                    spread = None if bid is None or ask is None else float(ask) - float(bid)
                    mid = None if bid is None or ask is None else (float(bid) + float(ask)) / 2.0
                    spread_bps = None
                    if fresh and spread is not None and spread >= 0 and mid is not None and mid > 0:
                        spread_bps = spread / mid * 10000.0
                    row[f"d{delay}s"] = {
                        "bid": bid,
                        "ask": ask,
                        "bid_timestamp_ms": bid_ts,
                        "ask_timestamp_ms": ask_ts,
                        "bid_age_ms": bid_age,
                        "ask_age_ms": ask_age,
                        "fresh": bool(fresh),
                        "spread": spread,
                        "spread_bps": spread_bps,
                    }
                rows.append(row)
        doc = {
            "schema": "mxm.research-core-v3.global-friction-triage-hour-evidence.v1",
            "design_binding_sha256": self.design["binding_sha256"],
            "source_plan_binding_sha256": self.plan["binding_sha256"],
            "symbol": symbol,
            "symbol_id": int(target["symbol_id"]),
            "region_sha256": str(target["region_sha256"]),
            "hour_start_ms": int(hour_start),
            "reference_window_count": int(reference_window_count),
            "sampled_window_count": len(windows),
            "unsampled_windows_contribute_zero_to_death_proxy": True,
            "transport_span_minutes": int(span_min),
            "rows": sorted(rows, key=lambda r: r["exact_window_index"]),
            "transport_provenance": provenance,
            "raw_ticks_persisted": False,
        }
        doc["binding_sha256"] = _sha_bytes(_canonical(doc))
        payload = _gzip_json_bytes(doc)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(path, payload)
        self.stage_state["completed_hours"][key] = {
            "sha256": _sha_bytes(payload),
            "rows": len(rows),
        }
        atomic_write_json(self.stage_state_path, self.stage_state)
        self._check_global_disk()
        return doc

    def _region_decision(
        self,
        symbol: str,
        target: Mapping[str, Any],
        sampling_meta: Mapping[str, Any],
    ) -> dict[str, Any]:
        gross = float(target["minimum_mean_response_bps"])
        totals: dict[str, list[float]] = {}
        coverage = {
            "fresh_nonnegative": 0,
            "missing_or_stale": 0,
            "negative": 0,
            "implicit_zero_unselected_within_sampled_hours": 0,
        }
        sampled_hours = 0
        sampled_windows = 0
        for stratum, meta in sampling_meta.items():
            values = []
            for hour_value in meta["selected_hour_start_ms"]:
                hour = int(hour_value)
                doc = _load_gzip_json(self._hour_file(symbol, hour))
                value, counts = self._cluster_total(doc, gross)
                values.append(value)
                sampled_hours += 1
                sampled_windows += len(doc["rows"])
                coverage["implicit_zero_unselected_within_sampled_hours"] += max(
                    0, int(doc["reference_window_count"]) - len(doc["rows"])
                )
                for key in ("fresh_nonnegative", "missing_or_stale", "negative"):
                    coverage[key] += counts[key]
            if values:
                totals[stratum] = values
        rule = self.design["death_rule"]
        bound = global_death_bound(
            gross_bps=gross,
            total_reference_windows=int(target["windows"]),
            strata_meta=sampling_meta,
            sampled_cluster_totals=totals,
            alpha=float(rule["per_region_alpha"]),
        )
        dead = bound["lower_bound_bps"] > gross
        return {
            "symbol": symbol,
            "region_sha256": str(target["region_sha256"]),
            "minimum_gross_mean_response_bps": gross,
            **bound,
            "sampled_hours": sampled_hours,
            "sampled_exact_windows": sampled_windows,
            "coverage": coverage,
            "decision": str(rule["death_label"] if dead else rule["nondeath_label"]),
            "candidate_frozen": False,
            "net_certification": False,
            "automatic_additional_acquisition": False,
        }

    def _run_global_triage(
        self,
        account_id: int,
        sampling_freeze: Mapping[str, Any],
        profile: Mapping[str, int],
    ) -> dict[str, Any]:
        targets = {str(t["symbol"]): t for t in self.plan["targets"]}
        symbol_order = [str(t["symbol"]) for t in self.plan["targets"]]
        reference_maps: dict[str, dict[int, tuple[ExactWindow, ...]]] = {}
        for symbol in symbol_order:
            strata = build_reference_strata(self.scope_by_symbol[symbol])
            hour_map: dict[int, tuple[ExactWindow, ...]] = {}
            for hours in strata.values():
                hour_map.update(hours)
            reference_maps[symbol] = hour_map

        all_strata = sorted(
            {
                stratum
                for symbol in symbol_order
                for stratum in sampling_freeze["sampling"][symbol]
            }
        )
        captured_regions: set[str] = set()
        for stratum in all_strata:
            for symbol in symbol_order:
                meta = sampling_freeze["sampling"][symbol].get(stratum)
                if not meta:
                    continue
                target = targets[symbol]
                for hour_value in meta["selected_hour_start_ms"]:
                    hour = int(hour_value)
                    chosen_ids = {
                        int(x)
                        for x in meta["selected_window_indices_by_hour"][str(hour)]
                    }
                    reference_windows = reference_maps[symbol][hour]
                    chosen = tuple(
                        w for w in reference_windows if int(w.index) in chosen_ids
                    )
                    if len(chosen) != len(chosen_ids):
                        raise CaptureContractError("frozen triage window membership mismatch")
                    self._stage(
                        f"[GLOBAL TRIAGE] {symbol} {stratum} "
                        f"sample_windows={len(chosen)} transport_span={profile[symbol]}m"
                    )
                    self._capture_triage_hour(
                        account_id,
                        target,
                        hour,
                        chosen,
                        int(profile[symbol]),
                        reference_window_count=int(
                            meta["reference_window_count_by_selected_hour"][str(hour)]
                        ),
                    )
                    captured_regions.add(symbol)

        if captured_regions != set(symbol_order):
            raise CaptureContractError("global triage did not acquire all 14 regions")

        self._stage("[GLOBAL TRIAGE] all 14 acquisition complete; evaluating jointly")
        decisions: dict[str, Any] = {}
        for symbol in symbol_order:
            decision = self._region_decision(
                symbol, targets[symbol], sampling_freeze["sampling"][symbol]
            )
            decisions[symbol] = decision
            self._stage(
                f"[DECISION] {symbol} {decision['decision']} "
                f"LCB={decision['lower_bound_bps']:.4f}bps "
                f"gross={decision['minimum_gross_mean_response_bps']:.4f}bps"
            )
        rule = self.design["death_rule"]
        return {
            "schema": "mxm.research-core-v3.global-friction-triage-decisions.v1",
            "design_binding_sha256": self.design["binding_sha256"],
            "familywise_alpha": float(rule["familywise_alpha"]),
            "per_region_alpha": float(rule["per_region_alpha"]),
            "campaign_looks": 1,
            "all_14_complete_before_joint_evaluation": True,
            "automatic_additional_acquisition": False,
            "regions": decisions,
            "protected_forward_opened": False,
            "candidate_frozen_count": 0,
        }

    def _finalize_global(
        self,
        benchmark: Mapping[str, Any],
        profile: Mapping[str, int],
        sampling_freeze: Mapping[str, Any],
        decisions: Mapping[str, Any],
        disk_start: Mapping[str, int],
    ) -> Path:
        if self.stage_output_dir.exists():
            shutil.rmtree(self.stage_output_dir)
        evidence = self.stage_output_dir / "evidence"
        derived = self.stage_output_dir / "derived"
        evidence.mkdir(parents=True, exist_ok=True)
        derived.mkdir(parents=True, exist_ok=True)
        atomic_write_json(evidence / "stage0_benchmark.json", dict(benchmark))
        atomic_write_json(
            evidence / "transport_profile.json",
            {
                "schema": "mxm.research-core-v3.global-friction-triage-transport-profile.v1",
                "design_binding_sha256": self.design["binding_sha256"],
                "recommended_span_minutes_by_symbol": dict(profile),
                "economic_outcomes_used": False,
            },
        )
        atomic_write_json(evidence / "sampling_freeze.json", dict(sampling_freeze))
        atomic_write_json(evidence / "region_decisions.json", dict(decisions))
        for target in self.plan["targets"]:
            symbol = str(target["symbol"])
            files = sorted((self.hours_dir / symbol).glob("*.json.gz"))
            out = derived / f"{symbol}_GLOBAL_TRIAGE_HOURS.jsonl.gz"
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
        disk_end = self._check_global_disk()
        storage = self.design["storage"]
        manifest = {
            "schema": "mxm.research-core-v3.global-friction-triage-evidence-bundle.v1",
            "design_binding_sha256": self.design["binding_sha256"],
            "source_plan_binding_sha256": self.plan["binding_sha256"],
            "account_fingerprint_sha256": self.plan["broker_identity"][
                "accepted_account_fingerprint_sha256"
            ],
            "corrected_development_cells": 7975,
            "gross_robust_regions": 88,
            "priority_regions": 14,
            "other_gross_regions_cost_unresolved": 74,
            "authoritative_frontier": 1576,
            "protected_forward_opened": False,
            "candidate_frozen_count": 0,
            "raw_ticks_embedded_in_transfer_bundle": False,
            "raw_tick_values_written_to_disk": False,
            "stage0_economic_values_recorded": False,
            "automatic_additional_acquisition": False,
            "storage": {
                "aggregate_capture_bytes_at_start": int(
                    disk_start["aggregate_capture_bytes"]
                ),
                "aggregate_capture_bytes_before_bundle": int(
                    disk_end["aggregate_capture_bytes"]
                ),
                "peak_local_capture_bytes": int(self._peak_local_bytes),
                "aggregate_local_hard_cap_bytes": int(
                    storage["aggregate_local_capture_artifacts_hard_cap_bytes"]
                ),
                "preferred_bundle_bytes": int(storage["preferred_first_bundle_size_bytes"]),
                "hard_bundle_cap_bytes": int(storage["hard_first_bundle_cap_bytes"]),
            },
            "interpretation": (
                "One frozen global DEVELOPMENT friction triage completed for all 14. "
                "A lower proxy can prove spread-alone economic death. Non-death means "
                "PLAUSIBLE_OR_UNRESOLVED only. No Look2/Look3/Look4, candidate freeze, "
                "or net certification is automatic."
            ),
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
        bundle_sha = deterministic_zip_directory(self.stage_output_dir, self.stage_bundle_path)
        with zipfile.ZipFile(self.stage_bundle_path) as archive:
            bad = archive.testzip()
            if bad:
                raise CaptureContractError(f"global triage bundle ZIP CRC failed: {bad}")
        bundle_bytes = self.stage_bundle_path.stat().st_size
        if bundle_bytes > int(storage["hard_first_bundle_cap_bytes"]):
            raise CaptureContractError("global triage bundle exceeded 64MiB hard cap")
        self._check_global_disk()
        self._stage(
            f"[GLOBAL TRIAGE COMPLETE] {self.stage_bundle_path.name} "
            f"sha256={bundle_sha} bytes={bundle_bytes} "
            f"peak_local={self._peak_local_bytes/1024/1024:.1f}MiB"
        )
        return self.stage_bundle_path

    def run_triage(self) -> Path:
        disk_start = self._check_global_disk()
        sampling_freeze, benchmark_freeze = self._reference()
        atomic_write_json(self.stage_work_dir / "sampling_freeze.json", sampling_freeze)
        atomic_write_json(self.stage_work_dir / "benchmark_freeze.json", benchmark_freeze)
        account_id = self._authenticate_and_verify_targets()
        benchmark, profile = self._run_stage0(account_id, benchmark_freeze)
        atomic_write_json(self.stage_work_dir / "stage0_benchmark.json", benchmark)
        atomic_write_json(self.stage_work_dir / "transport_profile.json", profile)
        decisions = self._run_global_triage(account_id, sampling_freeze, profile)
        atomic_write_json(self.stage_work_dir / "region_decisions.json", decisions)
        return self._finalize_global(
            benchmark, profile, sampling_freeze, decisions, disk_start
        )


def global_triage_geometry_preflight(repo_root: Path | str) -> dict[str, Any]:
    runner = object.__new__(GlobalFrictionTriageRunner)
    runner.repo_root = Path(repo_root)
    runner.plan_path = (
        runner.repo_root
        / "research_core_v3/state/MAXT14_AUTHENTIC_FRICTION_ACQUISITION_PLAN_V2.json"
    )
    runner.plan = json.loads(runner.plan_path.read_text(encoding="utf-8"))
    runner._validate_plan()
    runner.scope_by_symbol = runner._load_scopes_and_blocks()
    runner.design_path = runner.repo_root / DESIGN_REL
    runner.design = json.loads(runner.design_path.read_text(encoding="utf-8"))
    runner._validate_global_design()
    sampling_freeze, _ = runner._reference()

    spans = [180, 60, 15, 5, 1]
    by_span: dict[str, Any] = {}
    total_hours = 0
    total_windows = 0
    for span_min in spans:
        blocks = 0
        hours_count = 0
        windows_count = 0
        span_ms = span_min * 60_000
        buckets_per_hour = max(1, HOUR_MS // span_ms)
        for target in runner.plan["targets"]:
            symbol = str(target["symbol"])
            strata = build_reference_strata(runner.scope_by_symbol[symbol])
            meta_by_stratum = sampling_freeze["sampling"][symbol]
            for stratum, meta in meta_by_stratum.items():
                for hour_value in meta["selected_hour_start_ms"]:
                    hour = int(hour_value)
                    chosen_ids = {
                        int(x)
                        for x in meta["selected_window_indices_by_hour"][str(hour)]
                    }
                    chosen = [
                        w for w in strata[stratum][hour] if int(w.index) in chosen_ids
                    ]
                    hours_count += 1
                    windows_count += len(chosen)
                    occupied = {
                        int(
                            max(
                                0,
                                min(
                                    (w.boundary_ms - hour) // span_ms,
                                    buckets_per_hour - 1,
                                ),
                            )
                        )
                        for w in chosen
                    }
                    blocks += len(occupied)
        by_span[str(span_min)] = {
            "sampled_hours": hours_count,
            "sampled_exact_windows": windows_count,
            "transport_blocks": blocks,
            "base_bid_ask_requests_before_pagination": 2 * blocks,
        }
        total_hours = hours_count
        total_windows = windows_count

    stage0 = int(runner.design["stage0_benchmark"]["planned_base_probes"])
    eligible = [str(x) for x in runner.design["stage0_benchmark"]["stage1_eligible_spans_minutes"]]
    base_requests = [
        stage0 + int(by_span[k]["base_bid_ask_requests_before_pagination"])
        for k in eligible
    ]
    rate = float(runner.design["observed_v5_baseline"]["observed_base_chunk_rate_per_second"])
    return {
        "schema": "mxm.research-core-v3.global-friction-triage-geometry.v1",
        "design_binding_sha256": runner.design["binding_sha256"],
        "reference_exact_windows": 691_919,
        "sampled_hours": total_hours,
        "sampled_exact_windows": total_windows,
        "stage0_base_probes": stage0,
        "by_transport_span_minutes": by_span,
        "eligible_stage1_spans_minutes": [int(x) for x in eligible],
        "total_base_request_range_before_pagination": [min(base_requests), max(base_requests)],
        "base_only_seconds_at_observed_v5_rate_range": [
            min(base_requests) / rate,
            max(base_requests) / rate,
        ],
        "campaign_looks": 1,
        "automatic_additional_acquisition": False,
    }
