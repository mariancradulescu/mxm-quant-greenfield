"""Final pre-run runtime hardening for the accepted cTrader Open API adapter.

The accepted checkpoint implementation is preserved byte-for-byte in
``m6._ctrader_openapi_base``.  This module keeps its read-only protocol behavior and adds
no-credential SDK preflight, compact request/chunk progress, completion-boundary audit
fields, and final transferable-bundle completeness validation.
"""
from __future__ import annotations

import inspect
import sys
import time
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any, Mapping

from ctrader_open_api import Client, EndPoints, TcpProtocol

from . import _ctrader_openapi_base as _base
from ._ctrader_openapi_base import *  # noqa: F401,F403 - accepted runtime re-export
from .ctrader_capture import (
    HISTORICAL_TARGET_RPS,
    PROTECTED_FORWARD_START,
    CaptureContractError,
    atomic_write_json,
    format_capture_progress,
    gap_diagnostics,
    historical_windows,
    load_resume_state,
    merge_chunk_rows,
    next_pagination_to_ms,
    normalize_trendbars,
    raw_csv_bytes,
    record_completed_chunk,
    scan_bundle_for_secrets,
    sha256_file,
    validate_transferable_bundle,
    validate_transferable_zip,
    verified_chunk_path,
)

TOOL_VERSION = "MXM_M6_CTRADER_CAPTURE_V2"
BUNDLE_SCHEMA = _base.BUNDLE_SCHEMA


def runtime_sdk_preflight() -> dict[str, Any]:
    """Import/construct the pinned official SDK without network or credentials."""
    if not callable(getattr(TcpProtocol, "heartbeat", None)):
        raise CaptureContractError("installed cTrader SDK TcpProtocol heartbeat() is unavailable")
    try:
        sender_source = inspect.getsource(TcpProtocol._sendStrings)
    except (OSError, TypeError) as exc:
        raise CaptureContractError("cannot inspect installed cTrader SDK heartbeat loop") from exc
    if "heartbeat" not in sender_source:
        raise CaptureContractError("installed cTrader SDK idle send loop does not expose heartbeat path")
    if not EndPoints.PROTOBUF_LIVE_HOST or int(EndPoints.PROTOBUF_PORT) <= 0:
        raise CaptureContractError("installed cTrader SDK LIVE endpoint metadata is invalid")
    probe = Client(
        EndPoints.PROTOBUF_LIVE_HOST,
        EndPoints.PROTOBUF_PORT,
        TcpProtocol,
        numberOfMessagesToSendPerSecond=45,
    )
    if probe is None:
        raise CaptureContractError("cTrader SDK Client construction failed")
    return {
        "ctrader_open_api_version": package_version("ctrader-open-api"),
        "live_host": EndPoints.PROTOBUF_LIVE_HOST,
        "live_port": int(EndPoints.PROTOBUF_PORT),
        "tcp_protocol_heartbeat_available": True,
        "sdk_idle_heartbeat_path_verified": True,
        "network_connection_attempted": False,
        "credentials_used": False,
    }


class OpenApiCaptureRunner(_base.OpenApiCaptureRunner):
    """Accepted read-only runner with final Android progress and bundle hardening."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._run_started_monotonic = time.monotonic()
        self._historical_started_monotonic: float | None = None
        self._historical_requests_completed = 0
        self._resume_reused_chunks = 0
        self._progress_line_active = False
        self._progress_line_width = 0
        self._last_overall_percent = 0.0

    def _finish_progress_line(self) -> None:
        if self._progress_line_active and self.progress is print:
            sys.stdout.write("\n")
            sys.stdout.flush()
        self._progress_line_active = False
        self._progress_line_width = 0

    def _stage(self, text: str) -> None:
        self._finish_progress_line()
        self.progress(text)

    def _emit_live_progress(
        self, *, overall_percent: float, stage: str, instrument: str, resolution: str,
        series_percent: float, completed_windows: int, total_windows: int,
        completed_chunks: int, rows_captured: int,
    ) -> None:
        overall = max(self._last_overall_percent, min(99.9, overall_percent))
        self._last_overall_percent = overall
        elapsed = time.monotonic() - self._run_started_monotonic
        if self._historical_started_monotonic is None:
            effective_rps = 0.0
        else:
            hist_elapsed = max(1e-9, time.monotonic() - self._historical_started_monotonic)
            effective_rps = self._historical_requests_completed / hist_elapsed
        line = format_capture_progress(
            overall_percent=overall,
            stage=stage,
            instrument=instrument,
            resolution=resolution,
            series_percent=series_percent,
            completed_windows=completed_windows,
            total_windows=total_windows,
            completed_chunks=completed_chunks,
            historical_requests_completed=self._historical_requests_completed,
            rows_captured=rows_captured,
            elapsed_seconds=elapsed,
            effective_rps=effective_rps,
            reused_chunks=self._resume_reused_chunks,
            eta_seconds=None,
        )
        if self.progress is print:
            padded = line.ljust(self._progress_line_width)
            sys.stdout.write("\r" + padded)
            sys.stdout.flush()
            self._progress_line_width = max(self._progress_line_width, len(line))
            self._progress_line_active = True
        else:
            self.progress(line)

    @_base.defer.inlineCallbacks
    def _send(self, request, *, historical: bool = False, retries: int = 3):
        if historical and self._historical_started_monotonic is None:
            self._historical_started_monotonic = time.monotonic()
        result = yield super()._send(request, historical=historical, retries=retries)
        if historical:
            self._historical_requests_completed += 1
        return result

    def _connected(self, client):
        self._stage("[cTrader] LIVE transport connected; official SDK idle heartbeat remains enabled.")
        return super()._connected(client)

    def _disconnected(self, client, reason):
        self._finish_progress_line()
        return super()._disconnected(client, reason)

    def _done(self, result):
        self._finish_progress_line()
        return super()._done(result)

    def _failed(self, failure):
        self._finish_progress_line()
        return super()._failed(failure)

    @_base.defer.inlineCallbacks
    def _capture_series(self, *, account_id: int, symbol_id: int, resolution: str,
                        digits: int, capture_id: str, output_subdir: str):
        defaults = self.plan["raw_capture_defaults"]
        interval = defaults["interval"]
        state = load_resume_state(self.resume_path, self.plan_sha)
        series_work = self.work_dir / capture_id
        series_work.mkdir(parents=True, exist_ok=True)
        windows = historical_windows(interval["start_utc"], interval["end_utc"], resolution)
        total_windows = len(windows)
        chunk_paths: list[Path] = []
        completed_chunks = 0
        rows_so_far = 0
        if output_subdir == "raw":
            primary = self.plan["unique_raw_capture_tasks"]
            series_index = next(i for i, item in enumerate(primary) if item["raw_capture_id"] == capture_id)
            series_total = len(primary)
            stage_label = "PRIMARY"
            display_name = next(item["canonical_instrument"] for item in primary if item["raw_capture_id"] == capture_id)
            overall_base, overall_span = 40.0, 57.0
        else:
            series_index, series_total = 0, 1
            stage_label = "AUX-CONVERSION"
            display_name = capture_id.replace("PW02-AUX-CONV-", "").split("-M15-", 1)[0]
            overall_base, overall_span = max(23.0, self._last_overall_percent), max(0.0, 40.0 - max(23.0, self._last_overall_percent))

        for wi, (from_ms, window_to_ms) in enumerate(windows):
            page = 0
            page_to_ms = window_to_ms
            window_completed = False
            while page_to_ms >= from_ms:
                key = f"{capture_id}:{wi}:{page}:{from_ms}:{page_to_ms}"
                resumed = verified_chunk_path(state, key)
                if resumed is not None:
                    chunk_paths.append(resumed)
                    item = state["chunks"][key]
                    completed_chunks += 1
                    rows_so_far += int(item.get("row_count", 0))
                    self._resume_reused_chunks += 1
                    has_more = bool(item.get("has_more"))
                    next_to = item.get("next_to_ms")
                    if has_more and next_to is not None:
                        page_to_ms = int(next_to)
                        page += 1
                    else:
                        window_completed = True
                    series_fraction = (wi + (1.0 if window_completed else 0.0)) / max(1, total_windows)
                    if output_subdir == "raw":
                        overall = overall_base + overall_span * ((series_index + series_fraction) / series_total)
                    else:
                        overall = overall_base + overall_span * series_fraction
                    self._emit_live_progress(
                        overall_percent=overall, stage=stage_label, instrument=display_name,
                        resolution=resolution, series_percent=series_fraction * 100.0,
                        completed_windows=wi + (1 if window_completed else 0), total_windows=total_windows,
                        completed_chunks=completed_chunks, rows_captured=rows_so_far,
                    )
                    if window_completed:
                        break
                    continue

                req = _base.ProtoOAGetTrendbarsReq(
                    ctidTraderAccountId=account_id,
                    symbolId=int(symbol_id),
                    period=_base.ProtoOATrendbarPeriod.Value(resolution),
                    fromTimestamp=from_ms,
                    toTimestamp=page_to_ms,
                    count=5000,
                )
                res = yield self._send(req, historical=True)
                trendbars = [_base._plain(x) for x in res.trendbar]
                rows = normalize_trendbars(
                    trendbars,
                    resolution=resolution,
                    digits=digits,
                    requested_start_utc=interval["start_utc"],
                    requested_end_utc=interval["end_utc"],
                    protected_start_utc=PROTECTED_FORWARD_START,
                )
                chunk_path = series_work / f"w{wi:04d}_p{page:04d}.csv"
                chunk_path.write_bytes(raw_csv_bytes(rows))
                record_completed_chunk(
                    state,
                    chunk_key=key,
                    path=chunk_path,
                    raw_capture_id=capture_id,
                    request_from_ms=from_ms,
                    request_to_ms=page_to_ms,
                    page=page,
                    row_count=len(rows),
                )
                has_more = bool(getattr(res, "hasMore", False))
                next_to = next_pagination_to_ms(trendbars, from_ms) if has_more else None
                state["chunks"][key]["has_more"] = has_more
                state["chunks"][key]["next_to_ms"] = next_to
                atomic_write_json(self.resume_path, state)
                chunk_paths.append(chunk_path)
                completed_chunks += 1
                rows_so_far += len(rows)
                window_completed = not has_more
                series_fraction = (wi + (1.0 if window_completed else 0.0)) / max(1, total_windows)
                if output_subdir == "raw":
                    overall = overall_base + overall_span * ((series_index + series_fraction) / series_total)
                else:
                    overall = overall_base + overall_span * series_fraction
                self._emit_live_progress(
                    overall_percent=overall, stage=stage_label, instrument=display_name,
                    resolution=resolution, series_percent=series_fraction * 100.0,
                    completed_windows=wi + (1 if window_completed else 0), total_windows=total_windows,
                    completed_chunks=completed_chunks, rows_captured=rows_so_far,
                )
                if not has_more:
                    break
                if next_to is None or next_to >= page_to_ms:
                    raise CaptureContractError(f"{capture_id}: invalid historical pagination")
                page_to_ms = next_to
                page += 1

        rows = merge_chunk_rows(chunk_paths)
        out_dir = self.bundle_dir / output_subdir
        out_dir.mkdir(parents=True, exist_ok=True)
        final_path = out_dir / f"{capture_id}.csv"
        final_path.write_bytes(raw_csv_bytes(rows))
        return {
            "resolution": resolution,
            "requested_interval": interval,
            "row_count": len(rows),
            "first_timestamp_utc": rows[0]["time_utc"] if rows else None,
            "last_timestamp_utc": rows[-1]["time_utc"] if rows else None,
            "sha256": sha256_file(final_path),
            "file": final_path.relative_to(self.bundle_dir).as_posix(),
            "gap_diagnostics": gap_diagnostics(rows, resolution),
            "completed_bars_only": True,
            "development_completion_cutoff_enforced": True,
            "bar_completion_must_be_lte_requested_end": True,
            "bar_completion_must_be_lt_protected_start": True,
            "protected_forward_rows_included": False,
            "resampling_performed": False,
            "synthetic_fill_performed": False,
            "forward_fill_performed": False,
        }

    def _common_evidence_files(self):
        super()._common_evidence_files()
        evidence = self.bundle_dir / "evidence"
        atomic_write_json(evidence / "candidate_bindings.json", self.plan["candidate_dataset_bindings"])
        atomic_write_json(evidence / "gap_diagnostics.json", {
            "primary_raw": {
                key: value.get("gap_diagnostics") for key, value in sorted(self._raw_results.items())
            },
            "auxiliary_conversion_raw": {
                key: value.get("gap_diagnostics") for key, value in sorted(self._conversion_raw_results.items())
            },
            "gaps_are_reported_not_filled": True,
        })

    def _write_final_bundle(self):
        super()._write_final_bundle()
        validate_transferable_bundle(self.bundle_dir)
        validate_transferable_zip(self.bundle_dir.parent / f"{self.bundle_name}.zip")

    def run(self) -> Path:
        self._stage(
            f"[RATE] Historical target {HISTORICAL_TARGET_RPS:.2f} req/s "
            "(0.21 s pacing; official ceiling 5 req/s/connection)."
        )
        return super().run()
