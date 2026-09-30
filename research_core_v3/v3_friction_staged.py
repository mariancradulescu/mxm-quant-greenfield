"""Outcome-blind staged authentic friction acquisition for Research Core V3.

Stage 0 measures transport only. Stage 1 samples frozen DEVELOPMENT reference hours
prospectively and may stop only for a conservative spread-alone economic-death proof.
No favorable early stopping, no protected-forward access, no raw-tick transfer.
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from m6.cost_evidence import (
    BoundaryQuoteIndex,
    QUOTE_TYPES,
    atomic_write_bytes,
    decode_ctrader_tick_page,
    deterministic_zip_directory,
    next_tick_page_to_ms,
)
from m6.ctrader_capture import CaptureContractError, atomic_write_json, sha256_file
from m6.ctrader_proto.OpenApiMessages_pb2 import ProtoOAGetTickDataReq
from research_core_v3.v3_friction_capture import (
    BrokerHistoryUnavailable,
    ExactWindow,
    V3MaxT14FrictionRunner,
    _canonical,
    _sha_bytes,
)

DESIGN_REL = "research_core_v3/state/STAGED_FRICTION_ACQUISITION_PLAN_V1.json"
STAGE_WORK_REL = ".mxm_v3_staged_friction_work"
STAGE_OUTPUT_REL = "v3_friction_stage_output/MXM_V3_STAGED_FRICTION_EVIDENCE_V1"
STAGE_TRANSFER_NAME = "MXM_V3_STAGED_FRICTION_EVIDENCE_V1.zip"
HOUR_MS = 3_600_000


def _month_session_key(hour_start_ms: int) -> str:
    dt = datetime.fromtimestamp(hour_start_ms / 1000.0, tz=timezone.utc)
    return f"{dt.year:04d}-{dt.month:02d}|S{dt.hour // 6}"


def _dir_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def _gzip_json_bytes(value: Any) -> bytes:
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return gzip.compress(raw, compresslevel=9, mtime=0)


def _load_gzip_json(path: Path) -> Any:
    return json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))


def build_reference_strata(
    scope: Mapping[str, Any],
) -> dict[str, dict[int, tuple[ExactWindow, ...]]]:
    strata: dict[str, dict[int, list[ExactWindow]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for idx, (start_ms, end_ms) in enumerate(scope["windows"]):
        window = ExactWindow(index=idx, start_ms=int(start_ms), end_ms=int(end_ms))
        hour_start = (window.boundary_ms // HOUR_MS) * HOUR_MS
        strata[_month_session_key(hour_start)][hour_start].append(window)
    return {
        key: {hour: tuple(windows) for hour, windows in hours.items()}
        for key, hours in strata.items()
    }


def _hash_order(seed: str, symbol: str, stratum: str, hour_start: int) -> str:
    return hashlib.sha256(
        f"{seed}|{symbol}|{stratum}|{hour_start}".encode("utf-8")
    ).hexdigest()


def freeze_sampling_for_symbol(
    symbol: str,
    strata: Mapping[str, Mapping[int, tuple[ExactWindow, ...]]],
    *,
    seed: str,
    stage_counts: list[int],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for stratum in sorted(strata):
        hours = strata[stratum]
        ordered = sorted(
            hours, key=lambda h: (_hash_order(seed, symbol, stratum, h), h)
        )
        out[stratum] = {
            "reference_hours": len(ordered),
            "reference_windows": sum(len(hours[h]) for h in ordered),
            "max_windows_per_hour": max(
                (len(hours[h]) for h in ordered), default=0
            ),
            "ordered_hour_start_ms": ordered,
            "stage_hour_counts": [
                min(int(n), len(ordered)) for n in stage_counts
            ],
        }
    return out


def benchmark_anchor_hours(
    strata: Mapping[str, Mapping[int, tuple[ExactWindow, ...]]],
) -> list[int]:
    merged: dict[int, int] = {}
    for hours in strata.values():
        for hour, windows in hours.items():
            merged[hour] = len(windows)
    items = sorted(merged.items(), key=lambda x: (x[1], x[0]))
    if not items:
        return []
    selected: list[int] = []
    for q in (0.25, 0.50, 0.90):
        idx = int(round(q * (len(items) - 1)))
        choices = sorted(
            range(len(items)), key=lambda i: (abs(i - idx), items[i][0])
        )
        for i in choices:
            hour = items[i][0]
            if hour not in selected:
                selected.append(hour)
                break
    return selected


def staged_death_bound(
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
        raise CaptureContractError("invalid staged death-bound inputs")
    estimate = 0.0
    range_sq = 0.0
    used = 0
    for stratum, totals in sampled_cluster_totals.items():
        meta = strata_meta[stratum]
        population_hours = int(meta["reference_hours"])
        max_windows = int(meta["max_windows_per_hour"])
        sample_hours = len(totals)
        if population_hours <= 0 or sample_hours <= 0:
            continue
        if sample_hours > population_hours:
            raise CaptureContractError("sampled more hours than reference population")
        coeff = population_hours / (total_windows * sample_hours)
        estimate += coeff * sum(float(x) for x in totals)
        cluster_range = max_windows * (2.0 * gross)
        range_sq += sample_hours * (coeff * cluster_range) ** 2
        used += sample_hours
    if used == 0:
        return {
            "estimate_clipped_bps": 0.0,
            "half_width_bps": float("inf"),
            "lower_bound_bps": 0.0,
        }
    width = math.sqrt(0.5 * math.log(1.0 / alpha) * range_sq)
    return {
        "estimate_clipped_bps": estimate,
        "half_width_bps": width,
        "lower_bound_bps": max(0.0, estimate - width),
    }


class StagedFrictionRunner(V3MaxT14FrictionRunner):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.design_path = self.repo_root / DESIGN_REL
        if not self.design_path.is_file():
            raise CaptureContractError("staged friction design missing")
        self.design = json.loads(self.design_path.read_text(encoding="utf-8"))
        self._validate_design()
        self.stage_work_dir = self.repo_root / STAGE_WORK_REL
        self.stage_output_dir = self.repo_root / STAGE_OUTPUT_REL
        self.stage_bundle_path = self.stage_output_dir.parent / STAGE_TRANSFER_NAME
        self.stage_state_path = self.stage_work_dir / "state.json"
        self.hours_dir = self.stage_work_dir / "hours"
        self.stage_work_dir.mkdir(parents=True, exist_ok=True)
        self.hours_dir.mkdir(parents=True, exist_ok=True)
        self.stage_state = self._load_stage_state()
        self._peak_local_bytes = _dir_bytes(self.stage_work_dir)

    def _validate_design(self) -> None:
        design = self.design
        expected = design.get("binding_sha256")
        unsigned = dict(design)
        unsigned.pop("binding_sha256", None)
        if _sha_bytes(_canonical(unsigned)) != expected:
            raise CaptureContractError("staged design binding mismatch")
        if (
            design.get("status")
            != "FROZEN_OUTCOME_BLIND_STAGED_AUTHENTIC_FRICTION_DESIGN"
        ):
            raise CaptureContractError("staged design is not frozen")
        if design.get("source_plan_binding_sha256") != self.plan.get(
            "binding_sha256"
        ):
            raise CaptureContractError("staged design/source plan mismatch")
        scope = design["scope"]
        if int(scope["full_reference_exact_windows"]) != 691_919:
            raise CaptureContractError("staged reference-window count changed")
        if scope.get("protected_forward_opened") is not False:
            raise CaptureContractError("staged design opens protected-forward")
        if int(scope.get("candidate_frozen_count", -1)) != 0:
            raise CaptureContractError("staged design assumes frozen candidate")

    def _load_stage_state(self) -> dict[str, Any]:
        contract = {
            "schema": "mxm.research-core-v3.staged-friction-resume.v1",
            "design_binding_sha256": self.design["binding_sha256"],
            "source_plan_binding_sha256": self.plan["binding_sha256"],
            "accepted_account_fingerprint_sha256": self.plan["broker_identity"][
                "accepted_account_fingerprint_sha256"
            ],
        }
        contract["binding_sha256"] = _sha_bytes(_canonical(contract))
        if self.stage_state_path.is_file():
            try:
                state = json.loads(
                    self.stage_state_path.read_text(encoding="utf-8")
                )
            except Exception:
                state = None
            if isinstance(state, dict) and state.get("contract") == contract:
                return state
        state = {
            "schema": "mxm.research-core-v3.staged-friction-resume-state.v1",
            "contract": contract,
            "completed_hours": {},
        }
        atomic_write_json(self.stage_state_path, state)
        return state

    def _check_disk(self) -> dict[str, int]:
        usage = shutil.disk_usage(self.repo_root)
        local = _dir_bytes(self.stage_work_dir)
        self._peak_local_bytes = max(self._peak_local_bytes, local)
        policy = self.design["storage"]
        if usage.free < int(policy["minimum_free_disk_bytes"]):
            raise CaptureContractError("free disk below staged safety floor")
        if local > int(policy["stage_work_dir_hard_cap_bytes"]):
            raise CaptureContractError("staged work directory exceeded hard disk cap")
        return {
            "free_bytes": int(usage.free),
            "stage_work_bytes": int(local),
        }

    def _reference(self) -> tuple[dict[str, Any], dict[str, Any]]:
        stage_counts = [
            int(x)
            for x in self.design["stage1_sampling"][
                "stage_hours_per_nonempty_stratum"
            ]
        ]
        seed = str(self.design["source_plan_binding_sha256"])
        sampling: dict[str, Any] = {}
        anchors: dict[str, Any] = {}
        for target in self.plan["targets"]:
            symbol = str(target["symbol"])
            strata = build_reference_strata(self.scope_by_symbol[symbol])
            sampling[symbol] = freeze_sampling_for_symbol(
                symbol, strata, seed=seed, stage_counts=stage_counts
            )
            anchors[symbol] = benchmark_anchor_hours(strata)
        freeze = {
            "schema": "mxm.research-core-v3.staged-friction-sampling-freeze.v1",
            "design_binding_sha256": self.design["binding_sha256"],
            "source_plan_binding_sha256": self.plan["binding_sha256"],
            "sampling": sampling,
        }
        freeze["binding_sha256"] = _sha_bytes(_canonical(freeze))
        benchmark = {
            "schema": "mxm.research-core-v3.stage0-benchmark-freeze.v1",
            "design_binding_sha256": self.design["binding_sha256"],
            "anchors_by_symbol": anchors,
            "probe_spans_minutes": list(
                self.design["stage0_benchmark"]["probe_spans_minutes"]
            ),
        }
        benchmark["binding_sha256"] = _sha_bytes(_canonical(benchmark))
        return freeze, benchmark

    def _probe_range(
        self,
        account_id: int,
        target: Mapping[str, Any],
        side: str,
        start_ms: int,
        end_ms: int,
        *,
        keep_ticks: bool,
    ) -> tuple[list[Any], dict[str, Any]]:
        page_to = int(end_ms)
        previous_oldest = None
        ticks: list[Any] = []
        tick_count = 0
        pages = 0
        has_more_count = 0
        response_bytes = 0
        page_hashes: list[str] = []
        unavailable: list[dict[str, Any]] = []
        start_attempts = int(self._historical_attempts)
        start_transient = dict(self._transient_retry_counts)
        start_transport = int(self._transport_retry_count)
        started = time.monotonic()
        while page_to >= int(start_ms):
            req = ProtoOAGetTickDataReq(
                ctidTraderAccountId=int(account_id),
                symbolId=int(target["symbol_id"]),
                type=int(QUOTE_TYPES[side]),
                fromTimestamp=int(start_ms),
                toTimestamp=int(page_to),
            )
            try:
                response = self._send(req, historical=True)
            except BrokerHistoryUnavailable as exc:
                unavailable.append(
                    {
                        "from_ms": int(start_ms),
                        "to_ms": int(page_to),
                        "error_code": str(exc.code),
                        "description_sha256": hashlib.sha256(
                            str(exc.description or "").encode("utf-8")
                        ).hexdigest(),
                    }
                )
                break
            pages += 1
            blob = response.SerializeToString(deterministic=True)
            response_bytes += len(blob)
            page_hashes.append(hashlib.sha256(blob).hexdigest())
            decoded = decode_ctrader_tick_page(
                [
                    {"timestamp": int(x.timestamp), "tick": int(x.tick)}
                    for x in response.tickData
                ]
            )
            tick_count += len(decoded)
            if keep_ticks:
                ticks.extend(decoded)
            more = bool(getattr(response, "hasMore", False))
            if not more:
                break
            has_more_count += 1
            if not decoded:
                raise CaptureContractError(
                    "hasMore with empty page in staged acquisition"
                )
            oldest = min(x.timestamp_ms for x in decoded)
            next_to = next_tick_page_to_ms(
                decoded,
                current_from_ms=int(start_ms),
                previous_oldest_ms=previous_oldest,
            )
            if next_to is None:
                break
            previous_oldest = oldest
            if int(next_to) >= int(page_to):
                raise CaptureContractError(
                    "staged tick pagination did not progress"
                )
            page_to = int(next_to)
        transient_delta = {}
        for key, value in self._transient_retry_counts.items():
            diff = int(value) - int(start_transient.get(key, 0))
            if diff:
                transient_delta[key] = diff
        meta = {
            "side": side,
            "from_ms": int(start_ms),
            "to_ms": int(end_ms),
            "successful_api_responses": int(pages),
            "api_attempts": int(self._historical_attempts - start_attempts),
            "tick_count": int(tick_count),
            "protobuf_response_bytes": int(response_bytes),
            "has_more_count": int(has_more_count),
            "page_depth": int(pages),
            "elapsed_ms": int(round((time.monotonic() - started) * 1000)),
            "transient_retry_counts": transient_delta,
            "transport_retry_count": int(
                self._transport_retry_count - start_transport
            ),
            "broker_history_unavailable": unavailable,
            "page_response_sha256": page_hashes,
        }
        return ticks, meta

    def _run_stage0(
        self, account_id: int, benchmark_freeze: Mapping[str, Any]
    ) -> tuple[dict[str, Any], dict[str, int]]:
        self._stage(
            "[STAGE 0] transport/storage benchmark only; no spreads persisted"
        )
        records: list[dict[str, Any]] = []
        protected_ms = int(
            datetime.fromisoformat(
                self.plan["authority"]["protected_forward_start"].replace(
                    "Z", "+00:00"
                )
            ).timestamp()
            * 1000
        )
        spans = [
            int(x)
            for x in self.design["stage0_benchmark"]["probe_spans_minutes"]
        ]
        targets = {str(t["symbol"]): t for t in self.plan["targets"]}
        for symbol in sorted(benchmark_freeze["anchors_by_symbol"]):
            target = targets[symbol]
            reference_windows = self.scope_by_symbol[symbol]["windows"]
            development_min_ms = min(int(x[0]) for x in reference_windows)
            development_max_ms = max(int(x[1]) for x in reference_windows)
            for anchor_hour in benchmark_freeze["anchors_by_symbol"][symbol]:
                center = int(anchor_hour) + HOUR_MS // 2
                for span_min in spans:
                    span_ms = span_min * 60_000
                    start_ms = max(
                        development_min_ms, center - span_ms // 2
                    )
                    end_ms = min(
                        development_max_ms,
                        protected_ms - 1,
                        center + span_ms // 2,
                    )
                    if end_ms <= start_ms:
                        raise CaptureContractError(
                            "stage0 benchmark escaped DEVELOPMENT reference range"
                        )
                    for side in ("BID", "ASK"):
                        _, meta = self._probe_range(
                            account_id,
                            target,
                            side,
                            start_ms,
                            end_ms,
                            keep_ticks=False,
                        )
                        meta.update(
                            {
                                "symbol": symbol,
                                "symbol_id": int(target["symbol_id"]),
                                "anchor_hour_start_ms": int(anchor_hour),
                                "probe_span_minutes": span_min,
                            }
                        )
                        records.append(meta)
                        self._check_disk()
        profile: dict[str, int] = {}
        for symbol in sorted(targets):
            chosen = 5
            for candidate in (60, 15, 5):
                subset = [
                    r
                    for r in records
                    if r["symbol"] == symbol
                    and r["probe_span_minutes"] == candidate
                ]
                if (
                    subset
                    and not any(r["broker_history_unavailable"] for r in subset)
                    and max(r["page_depth"] for r in subset) <= 2
                ):
                    chosen = candidate
                    break
            profile[symbol] = chosen
        disk = self._check_disk()
        report = {
            "schema": "mxm.research-core-v3.stage0-transport-benchmark.v1",
            "design_binding_sha256": self.design["binding_sha256"],
            "benchmark_freeze_binding_sha256": benchmark_freeze[
                "binding_sha256"
            ],
            "economic_values_recorded": False,
            "raw_tick_values_persisted": False,
            "records": records,
            "summary": {
                "planned_base_probes": int(
                    self.design["stage0_benchmark"]["planned_base_probes"]
                ),
                "actual_probe_records": len(records),
                "successful_api_responses": sum(
                    r["successful_api_responses"] for r in records
                ),
                "api_attempts": sum(r["api_attempts"] for r in records),
                "ticks_returned": sum(r["tick_count"] for r in records),
                "protobuf_response_bytes": sum(
                    r["protobuf_response_bytes"] for r in records
                ),
                "has_more_count": sum(r["has_more_count"] for r in records),
                "transport_retry_count": sum(
                    r["transport_retry_count"] for r in records
                ),
                "broker_history_unavailable_events": sum(
                    len(r["broker_history_unavailable"]) for r in records
                ),
                "stage_work_bytes_after_benchmark": disk[
                    "stage_work_bytes"
                ],
                "free_disk_bytes_after_benchmark": disk["free_bytes"],
            },
            "recommended_transport_span_minutes_by_symbol": profile,
        }
        report["binding_sha256"] = _sha_bytes(_canonical(report))
        return report, profile

    def _split_windows(
        self,
        hour_start: int,
        windows: tuple[ExactWindow, ...],
        span_min: int,
    ) -> list[tuple[int, int, list[ExactWindow]]]:
        span_ms = int(span_min) * 60_000
        groups: dict[int, list[ExactWindow]] = defaultdict(list)
        buckets = max(1, HOUR_MS // span_ms)
        for window in windows:
            bucket = max(
                0,
                min(
                    (window.boundary_ms - hour_start) // span_ms,
                    buckets - 1,
                ),
            )
            groups[int(bucket)].append(window)
        return [
            (
                min(w.start_ms for w in groups[bucket]),
                max(w.end_ms for w in groups[bucket]),
                groups[bucket],
            )
            for bucket in sorted(groups)
        ]

    def _hour_file(self, symbol: str, hour_start: int) -> Path:
        return self.hours_dir / symbol / f"{hour_start}.json.gz"

    def _capture_hour(
        self,
        account_id: int,
        target: Mapping[str, Any],
        hour_start: int,
        windows: tuple[ExactWindow, ...],
        span_min: int,
    ) -> dict[str, Any]:
        symbol = str(target["symbol"])
        path = self._hour_file(symbol, hour_start)
        key = f"{symbol}|{hour_start}"
        saved = self.stage_state["completed_hours"].get(key)
        if (
            isinstance(saved, dict)
            and path.is_file()
            and sha256_file(path) == saved.get("sha256")
        ):
            return _load_gzip_json(path)
        rows: list[dict[str, Any]] = []
        provenance: list[dict[str, Any]] = []
        delays = [
            int(x)
            for x in self.design["stage1_sampling"][
                "delay_sensitivity_seconds"
            ]
        ]
        age_limit_ms = (
            int(
                self.design["stage1_sampling"][
                    "fresh_quote_age_limit_seconds"
                ]
            )
            * 1000
        )
        for start_ms, end_ms, block_windows in self._split_windows(
            hour_start, windows, span_min
        ):
            bids, bid_meta = self._probe_range(
                account_id,
                target,
                "BID",
                start_ms,
                end_ms,
                keep_ticks=True,
            )
            asks, ask_meta = self._probe_range(
                account_id,
                target,
                "ASK",
                start_ms,
                end_ms,
                keep_ticks=True,
            )
            index = BoundaryQuoteIndex(bids, asks)
            provenance.append(
                {
                    "from_ms": start_ms,
                    "to_ms": end_ms,
                    "bid": bid_meta,
                    "ask": ask_meta,
                }
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
                    bid_ok = (
                        state.bid_timestamp_ms is not None
                        and state.bid_timestamp_ms >= window.start_ms
                    )
                    ask_ok = (
                        state.ask_timestamp_ms is not None
                        and state.ask_timestamp_ms >= window.start_ms
                    )
                    bid = state.bid if bid_ok else None
                    ask = state.ask if ask_ok else None
                    bid_ts = state.bid_timestamp_ms if bid_ok else None
                    ask_ts = state.ask_timestamp_ms if ask_ok else None
                    bid_age = (
                        None if bid_ts is None else checkpoint - bid_ts
                    )
                    ask_age = (
                        None if ask_ts is None else checkpoint - ask_ts
                    )
                    fresh = (
                        bid is not None
                        and ask is not None
                        and bid_age is not None
                        and ask_age is not None
                        and max(bid_age, ask_age) <= age_limit_ms
                    )
                    spread = (
                        None
                        if bid is None or ask is None
                        else float(ask) - float(bid)
                    )
                    mid = (
                        None
                        if bid is None or ask is None
                        else (float(bid) + float(ask)) / 2.0
                    )
                    spread_bps = None
                    if (
                        fresh
                        and spread is not None
                        and spread >= 0
                        and mid is not None
                        and mid > 0
                    ):
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
            "schema": "mxm.research-core-v3.staged-hour-evidence.v1",
            "design_binding_sha256": self.design["binding_sha256"],
            "source_plan_binding_sha256": self.plan["binding_sha256"],
            "symbol": symbol,
            "symbol_id": int(target["symbol_id"]),
            "region_sha256": str(target["region_sha256"]),
            "hour_start_ms": int(hour_start),
            "reference_window_count": len(windows),
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
        self._check_disk()
        return doc

    def _cluster_total(
        self, doc: Mapping[str, Any], gross_bps: float
    ) -> tuple[float, dict[str, int]]:
        cap = 2.0 * float(gross_bps)
        total = 0.0
        counts = {
            "fresh_nonnegative": 0,
            "missing_or_stale": 0,
            "negative": 0,
        }
        for row in doc["rows"]:
            d0 = row["d0s"]
            value = d0.get("spread_bps")
            spread = d0.get("spread")
            if value is not None:
                total += min(float(value), cap)
                counts["fresh_nonnegative"] += 1
            elif spread is not None and float(spread) < 0:
                counts["negative"] += 1
            else:
                counts["missing_or_stale"] += 1
        return total, counts

    def _region_stage_decision(
        self,
        symbol: str,
        target: Mapping[str, Any],
        sampling_meta: Mapping[str, Any],
        stage_index: int,
    ) -> dict[str, Any]:
        gross = float(target["minimum_mean_response_bps"])
        stage_counts = self.design["stage1_sampling"][
            "stage_hours_per_nonempty_stratum"
        ]
        desired = int(stage_counts[stage_index])
        totals: dict[str, list[float]] = {}
        coverage = {
            "fresh_nonnegative": 0,
            "missing_or_stale": 0,
            "negative": 0,
        }
        for stratum, meta in sampling_meta.items():
            hours = [
                int(x)
                for x in meta["ordered_hour_start_ms"][
                    : min(desired, int(meta["reference_hours"]))
                ]
            ]
            values = []
            for hour in hours:
                doc = _load_gzip_json(self._hour_file(symbol, hour))
                value, counts = self._cluster_total(doc, gross)
                values.append(value)
                for key in coverage:
                    coverage[key] += counts[key]
            if values:
                totals[stratum] = values
        rule = self.design["sequential_rule"]
        bound = staged_death_bound(
            gross_bps=gross,
            total_reference_windows=int(target["windows"]),
            strata_meta=sampling_meta,
            sampled_cluster_totals=totals,
            alpha=float(rule["per_look_alpha"]),
        )
        precision_target = (
            float(rule["precision_target_half_width_fraction_of_gross"])
            * gross
        )
        dead = bound["lower_bound_bps"] > gross
        last = stage_index == len(stage_counts) - 1
        if dead:
            decision = (
                "CLEARLY_ECONOMICALLY_DEAD_STOP_MORE_CAPTURE_FOR_THIS_REGION"
            )
        elif last:
            decision = "INSUFFICIENT_KEEP_COST_UNRESOLVED"
        else:
            decision = "MARGINAL_EXPAND_SAMPLE"
        return {
            "symbol": symbol,
            "region_sha256": str(target["region_sha256"]),
            "stage_index": stage_index,
            "hours_per_nonempty_stratum_target": desired,
            "minimum_gross_mean_response_bps": gross,
            **bound,
            "precision_target_half_width_bps": precision_target,
            "precision_target_met": bool(
                bound["half_width_bps"] <= precision_target
            ),
            "coverage": coverage,
            "decision": decision,
            "candidate_frozen": False,
            "net_certification": False,
        }

    def _run_stage1(
        self,
        account_id: int,
        sampling_freeze: Mapping[str, Any],
        profile: Mapping[str, int],
    ) -> dict[str, Any]:
        targets = {str(t["symbol"]): t for t in self.plan["targets"]}
        all_decisions: dict[str, Any] = {}
        stage_counts = [
            int(x)
            for x in self.design["stage1_sampling"][
                "stage_hours_per_nonempty_stratum"
            ]
        ]
        for symbol in [str(t["symbol"]) for t in self.plan["targets"]]:
            target = targets[symbol]
            sampling_meta = sampling_freeze["sampling"][symbol]
            strata = build_reference_strata(self.scope_by_symbol[symbol])
            hour_map: dict[int, tuple[ExactWindow, ...]] = {}
            for hours in strata.values():
                hour_map.update(hours)
            history = []
            stopped = False
            for stage_index, desired in enumerate(stage_counts):
                if stopped:
                    break
                wanted: list[int] = []
                for meta in sampling_meta.values():
                    wanted.extend(
                        int(x)
                        for x in meta["ordered_hour_start_ms"][
                            : min(desired, int(meta["reference_hours"]))
                        ]
                    )
                wanted = sorted(set(wanted))
                self._stage(
                    f"[STAGE 1] {symbol} look={stage_index+1}/{len(stage_counts)} "
                    f"hours={len(wanted)} transport_span={profile[symbol]}m"
                )
                for hour in wanted:
                    self._capture_hour(
                        account_id,
                        target,
                        hour,
                        hour_map[hour],
                        int(profile[symbol]),
                    )
                decision = self._region_stage_decision(
                    symbol, target, sampling_meta, stage_index
                )
                history.append(decision)
                self._stage(
                    f"[DECISION] {symbol} {decision['decision']} | "
                    f"LCB={decision['lower_bound_bps']:.4f}bps "
                    f"gross={decision['minimum_gross_mean_response_bps']:.4f}bps "
                    f"halfwidth={decision['half_width_bps']:.4f}bps"
                )
                if (
                    decision["decision"]
                    == "CLEARLY_ECONOMICALLY_DEAD_STOP_MORE_CAPTURE_FOR_THIS_REGION"
                ):
                    stopped = True
            all_decisions[symbol] = {
                "looks": history,
                "final_decision": (
                    history[-1]["decision"]
                    if history
                    else "INSUFFICIENT_KEEP_COST_UNRESOLVED"
                ),
            }
        return {
            "schema": "mxm.research-core-v3.staged-friction-region-decisions.v1",
            "design_binding_sha256": self.design["binding_sha256"],
            "familywise_alpha": float(
                self.design["sequential_rule"]["familywise_alpha"]
            ),
            "per_look_alpha": float(
                self.design["sequential_rule"]["per_look_alpha"]
            ),
            "favorable_early_stop": False,
            "regions": all_decisions,
            "protected_forward_opened": False,
            "candidate_frozen_count": 0,
        }

    def _finalize(
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
                "schema": "mxm.research-core-v3.staged-transport-profile.v1",
                "design_binding_sha256": self.design["binding_sha256"],
                "recommended_span_minutes_by_symbol": dict(profile),
                "economic_outcomes_used": False,
            },
        )
        atomic_write_json(
            evidence / "sampling_freeze.json", dict(sampling_freeze)
        )
        atomic_write_json(evidence / "region_decisions.json", dict(decisions))
        for target in self.plan["targets"]:
            symbol = str(target["symbol"])
            files = sorted((self.hours_dir / symbol).glob("*.json.gz"))
            out = derived / f"{symbol}_STAGED_HOURS.jsonl.gz"
            with gzip.open(
                out, "wt", encoding="utf-8", compresslevel=9
            ) as handle:
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
            "schema": "mxm.research-core-v3.staged-friction-evidence-bundle.v1",
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
            "storage": {
                "free_disk_bytes_at_start": int(disk_start["free_bytes"]),
                "stage_work_bytes_at_start": int(
                    disk_start["stage_work_bytes"]
                ),
                "stage_work_bytes_at_finalize": int(
                    disk_end["stage_work_bytes"]
                ),
                "peak_stage_work_bytes": int(self._peak_local_bytes),
                "hard_cap_bytes": int(
                    self.design["storage"]["stage_work_dir_hard_cap_bytes"]
                ),
            },
            "interpretation": (
                "Stage 0 is transport-only. Stage 1 can stop early only for a "
                "conservative spread-alone death proof. Non-death remains "
                "COST_UNRESOLVED and is not net certification."
            ),
        }
        manifest["binding_sha256"] = _sha_bytes(_canonical(manifest))
        atomic_write_json(evidence / "manifest.json", manifest)
        checks = []
        for path in sorted(
            p for p in self.stage_output_dir.rglob("*") if p.is_file()
        ):
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
                    f"staged bundle ZIP CRC failed: {bad}"
                )
        self._stage(
            f"[STAGED COMPLETE] {self.stage_bundle_path.name} "
            f"sha256={bundle_sha} "
            f"peak_local={self._peak_local_bytes/1024/1024:.1f}MiB"
        )
        return self.stage_bundle_path

    def run_staged(self) -> Path:
        disk_start = self._check_disk()
        sampling_freeze, benchmark_freeze = self._reference()
        atomic_write_json(
            self.stage_work_dir / "sampling_freeze.json", sampling_freeze
        )
        atomic_write_json(
            self.stage_work_dir / "benchmark_freeze.json", benchmark_freeze
        )
        account_id = self._authenticate_and_verify_targets()
        benchmark, profile = self._run_stage0(account_id, benchmark_freeze)
        atomic_write_json(
            self.stage_work_dir / "stage0_benchmark.json", benchmark
        )
        atomic_write_json(
            self.stage_work_dir / "transport_profile.json", profile
        )
        decisions = self._run_stage1(
            account_id, sampling_freeze, profile
        )
        atomic_write_json(
            self.stage_work_dir / "region_decisions.json", decisions
        )
        return self._finalize(
            benchmark, profile, sampling_freeze, decisions, disk_start
        )


def staged_geometry_preflight(repo_root: Path | str) -> dict[str, Any]:
    """No-network exact staged sampling/transport geometry for CI and estimates."""
    runner = object.__new__(StagedFrictionRunner)
    runner.repo_root = Path(repo_root)
    runner.plan_path = runner.repo_root / "research_core_v3/state/MAXT14_AUTHENTIC_FRICTION_ACQUISITION_PLAN_V2.json"
    runner.plan = json.loads(runner.plan_path.read_text(encoding="utf-8"))
    runner._validate_plan()
    runner.scope_by_symbol = runner._load_scopes_and_blocks()
    runner.design_path = runner.repo_root / DESIGN_REL
    runner.design = json.loads(runner.design_path.read_text(encoding="utf-8"))
    runner._validate_design()
    sampling_freeze, _ = runner._reference()
    stage_counts = [
        int(x)
        for x in runner.design["stage1_sampling"][
            "stage_hours_per_nonempty_stratum"
        ]
    ]
    by_stage: list[dict[str, Any]] = []
    for desired in stage_counts:
        record: dict[str, Any] = {
            "hours_per_nonempty_stratum": desired,
            "by_transport_span_minutes": {},
        }
        for span_min in (60, 15, 5):
            total_hours = total_windows = total_blocks = 0
            span_ms = span_min * 60_000
            buckets_per_hour = max(1, HOUR_MS // span_ms)
            for target in runner.plan["targets"]:
                symbol = str(target["symbol"])
                strata = build_reference_strata(runner.scope_by_symbol[symbol])
                meta = sampling_freeze["sampling"][symbol]
                for stratum, smeta in meta.items():
                    selected = [
                        int(x)
                        for x in smeta["ordered_hour_start_ms"][
                            : min(desired, int(smeta["reference_hours"]))
                        ]
                    ]
                    total_hours += len(selected)
                    for hour in selected:
                        windows = strata[stratum][hour]
                        total_windows += len(windows)
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
                            for w in windows
                        }
                        total_blocks += len(occupied)
            record["by_transport_span_minutes"][str(span_min)] = {
                "sampled_hours": total_hours,
                "sampled_exact_windows": total_windows,
                "transport_blocks": total_blocks,
                "base_bid_ask_requests_before_pagination": 2 * total_blocks,
            }
        by_stage.append(record)
    return {
        "schema": "mxm.research-core-v3.staged-friction-geometry.v1",
        "design_binding_sha256": runner.design["binding_sha256"],
        "reference_exact_windows": 691_919,
        "stage0_base_probes": int(
            runner.design["stage0_benchmark"]["planned_base_probes"]
        ),
        "stages": by_stage,
    }
