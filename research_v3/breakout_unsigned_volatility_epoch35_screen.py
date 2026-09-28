"""Prospectively frozen, non-economic Epoch35 unsigned-volatility screen."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import statistics
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "MXM_EPOCH35_BREAKOUT_UNSIGNED_VOLATILITY_STRUCTURAL_SCREEN_V1"
FREEZE_REF = "research_v3/EPOCH35_BREAKOUT_UNSIGNED_VOLATILITY_FRONTIER_FREEZE_V1.json"
PROPOSAL_REF = "research_v3/ai_director/proposals/AUTO_reason_a723ef9a2bc53e57b7cb2acddd9e2477.json"
PROPOSAL_SHA256 = "06edd1a32863782b2f116254ad094f6a0615155db28c6e4869f4e9080ec4741b"
CURRENT_FRONTIER_REF = "research_v3/CURRENT_RESEARCH_FRONTIER_V1.json"
CURRENT_FRONTIER_SHA256 = "2e8cbe434a776d36ec494e7fbd642c36098400c38132cb57c734d6a60ab0f69b"
REGISTRY_REF = "research_v3/CURRENT_BROKER_STRUCTURAL_SIGNATURE_REGISTRY_EPOCH22_V1.json"
REGISTRY_SHA256 = "bd375406a1363704b5c6d0a76552d33b9d18d03f255c5f2c328c918c99b73ed3"
COVERAGE_REF = "evidence/CURRENT_FRONTIER_REPLACEMENT_13W_M5_STRUCTURAL_COVERAGE_EPOCH23_V1.json"
COVERAGE_SHA256 = "5cfb0662b12f1f42f8f5c503df64f42716dab98ba5729ab7e6eef75bce2c5dec"
DEVELOPMENT_ACCEPTANCE_REF = "data/BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_ACCEPTANCE_V1.json"
REPLACEMENT_ACCEPTANCE_REF = "evidence/CURRENT_FRONTIER_REPLACEMENT_13W_M5_CAPTURE_EPOCH23_ACCEPTANCE_V1.json"
DEVELOPMENT_SHA256 = "64ea52126a31c527d2021a50923adab1b7df8f0ce5debe7f631cf4ce09b39503"
REPLACEMENT_SHA256 = "d9be18c7aa902a83bad0417bc561b7ef8df4c3ac357ff884d98c4ee3e0cc5d75"
REPLACEMENT_IDS = frozenset({7427, 5352, 2924})
SUPERSEDED_DEVELOPMENT_IDS = frozenset({2922, 5348})  # Crude-F, HEXAB.SE; absent from the current 41.
M5_SECONDS = 300
LOOKBACK_BARS = 20
HORIZON_BARS = 6
MIN_DATES_PER_HALF = 10
FDR = 0.05
CSV_FIELDS = ["time_utc", "open", "high", "low", "close", "tick_volume"]
RESULT_REF = "evidence/EPOCH35_BREAKOUT_UNSIGNED_VOLATILITY_PERSISTENCE_STRUCTURAL_RESULT_V1.json"


class Epoch35ScreenError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Epoch35ScreenError(f"{path}: expected JSON object")
    return value


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Epoch35ScreenError(f"invalid UTC timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise Epoch35ScreenError(f"timestamp lacks timezone: {value!r}")
    return parsed.astimezone(timezone.utc)


def validate_freeze(freeze: dict[str, Any], root: Path) -> dict[str, Any]:
    if (freeze.get("schema") != "mxm.greenfield.epoch35-breakout-unsigned-volatility-frontier-freeze.v1"
            or freeze.get("status") != "PROSPECTIVELY_FROZEN_BEFORE_EPOCH35_UNSIGNED_VOLATILITY_SCREEN"
            or freeze.get("evidence_epoch") != 35):
        raise Epoch35ScreenError("unsupported or unfrozen Epoch35 authority")
    authority = freeze.get("authority") or {}
    expected_authority = {
        "accepted_proposal_ref": PROPOSAL_REF,
        "accepted_proposal_file_sha256": PROPOSAL_SHA256,
        "current_frontier_ref": CURRENT_FRONTIER_REF,
        "current_frontier_sha256": CURRENT_FRONTIER_SHA256,
        "registry_ref": REGISTRY_REF,
        "registry_sha256": REGISTRY_SHA256,
        "coverage_ref": COVERAGE_REF,
        "coverage_sha256": COVERAGE_SHA256,
        "development_acceptance_ref": DEVELOPMENT_ACCEPTANCE_REF,
        "development_zip_filename": "MXM_BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_V1.zip",
        "development_zip_sha256": DEVELOPMENT_SHA256,
        "replacement_acceptance_ref": REPLACEMENT_ACCEPTANCE_REF,
        "replacement_zip_filename": "MXM_CURRENT_FRONTIER_REPLACEMENT_13W_M5_V1.zip",
        "replacement_zip_sha256": REPLACEMENT_SHA256,
    }
    if any(authority.get(key) != value for key, value in expected_authority.items()):
        raise Epoch35ScreenError("Epoch35 authority binding mismatch")
    for ref, expected in (
        (PROPOSAL_REF, PROPOSAL_SHA256),
        (CURRENT_FRONTIER_REF, CURRENT_FRONTIER_SHA256),
        (REGISTRY_REF, REGISTRY_SHA256),
        (COVERAGE_REF, COVERAGE_SHA256),
    ):
        path = root / ref
        if not path.is_file() or sha256_file(path) != expected:
            raise Epoch35ScreenError(f"bound authority hash mismatch: {ref}")
    proposal = _load_json(root / PROPOSAL_REF)
    if proposal.get("proposal_id") != "epoch35-breakout-volatility-clustering":
        raise Epoch35ScreenError("accepted proposal identity mismatch")
    decision = proposal.get("decision") or {}
    frozen_method = decision.get("frozen_method") or {}
    if (proposal.get("schema") != "mxm.greenfield.general-ai-research-proposal.v1"
            or proposal.get("data_policy", {}).get("new_market_data_requested") is not False
            or frozen_method.get("input") != "Already accepted 13-week M5 captures only; use strictly prior completed bars to identify events."
            or frozen_method.get("outcome") != (
                "Compare realized variance from the next six completed M5 returns with realized variance "
                "from the six completed returns immediately before bar t; direction is ignored."
            )):
        raise Epoch35ScreenError("accepted proposal scope or unsigned-volatility estimand mismatch")
    current = _load_json(root / CURRENT_FRONTIER_REF)
    if (current.get("current_structural_registry_ref") != REGISTRY_REF
            or current.get("evidence_epoch") != 28):
        raise Epoch35ScreenError("bound registry no longer resolves through the frozen current frontier")
    registry = _load_json(root / REGISTRY_REF)
    representatives = registry.get("representatives")
    if (registry.get("status") != "CURRENT_STRUCTURAL_FRONTIER_RECOMPUTED_FROM_ACCEPTED_BROKER_NATIVE_METADATA"
            or registry.get("counts", {}).get("representative_count") != 41
            or not isinstance(representatives, list) or len(representatives) != 41):
        raise Epoch35ScreenError("Epoch35 requires the complete current 41-representative registry")
    symbols = [item.get("broker_symbol") for item in representatives]
    ids = [item.get("symbol_id") for item in representatives]
    if (len(set(symbols)) != 41 or len(set(ids)) != 41
            or not all(isinstance(value, str) and value for value in symbols)
            or not all(isinstance(value, int) for value in ids)):
        raise Epoch35ScreenError("registry contains missing or duplicate symbol identities")
    coverage = _load_json(root / COVERAGE_REF)
    if (coverage.get("status") != "COMPLETE_NON_ECONOMIC_CURRENT_REPRESENTATIVE_COVERAGE_RESTORED"
            or coverage.get("current_representative_history_coverage", {}).get("status") != "PASS_41_OF_41"):
        raise Epoch35ScreenError("accepted 13-week history coverage is not complete for the 41-symbol panel")
    development_acceptance = _load_json(root / DEVELOPMENT_ACCEPTANCE_REF)
    replacement_acceptance = _load_json(root / REPLACEMENT_ACCEPTANCE_REF)
    if (development_acceptance.get("status") != "ACCEPTED_COMPLETE_NON_ECONOMIC_DEVELOPMENT_CAPTURE"
            or development_acceptance.get("source", {}).get("zip_sha256") != DEVELOPMENT_SHA256
            or development_acceptance.get("validation", {}).get("series_complete") != 40
            or replacement_acceptance.get("status") != "ACCEPTED_AFTER_DETERMINISTIC_CANONICALIZATION_OF_IDENTICAL_DUPLICATES"
            or replacement_acceptance.get("capture_provenance", {}).get("returned_transport_zip_sha256") != REPLACEMENT_SHA256):
        raise Epoch35ScreenError("accepted capture records do not bind the exact frozen archives")

    scope = freeze.get("scope") or {}
    if (scope.get("frontier") != "ALL_41_CURRENT_STRUCTURAL_REPRESENTATIVES_EXACTLY_ONCE"
            or scope.get("representative_count") != 41
            or scope.get("representatives_are_not_economically_equivalent") is not True
            or scope.get("resolution") != "M5"
            or scope.get("interval") != {
                "start_utc": "2026-06-15T00:00:00Z",
                "end_utc": "2026-09-13T23:59:59Z",
            }
            or scope.get("development_representative_count") != 38
            or scope.get("replacement_representative_ids") != [7427, 5352, 2924]
            or scope.get("selection_law") != "PROCESS_ALL_41_CURRENT_REGISTRY_REPRESENTATIVES_WITHOUT_OUTCOME_BASED_SUBSETTING"
            or set(REPLACEMENT_IDS) - set(ids)):
        raise Epoch35ScreenError("frozen Epoch35 data and frontier scope mismatch")
    law = freeze.get("preregistered_structural_law") or {}
    inference = law.get("inference") or {}
    if (law.get("event") != (
                "At close of bar t, current high-low range is at least 2 times the median high-low range "
                "of the preceding 20 completed bars."
            )
            or law.get("event_lookback_bars") != LOOKBACK_BARS
            or law.get("event_range_multiple") != 2.0
            or law.get("zero_range_policy") != (
                "Require the current bar range to be positive; when prior median range is zero, "
                "any positive current range meets the frozen multiple threshold."
            )
            or law.get("outcome") != (
                "Compare the sum of squared log close-to-close returns over the next six completed M5 returns "
                "with the sum over the six completed M5 returns immediately preceding and ending at bar t."
            )
            or law.get("causal_timing") != (
                "Only completed bars at or before t identify the event and baseline; forward returns "
                "use only bars t+1 through t+6."
            )
            or law.get("independence") != (
                "Retain at most one event per symbol per UTC date: the first qualifying event with "
                "complete contiguous event, baseline, and forward windows and positive realized variance in both windows."
            )
            or law.get("daily_statistic") != "For each retained event/date, compute log(forward realized variance / baseline realized variance)."
            or inference.get("minimum_eligible_dates_per_half") != MIN_DATES_PER_HALF
            or inference.get("partition") != (
                "Sort eligible UTC event dates chronologically; first floor(N/2) dates are half 1 "
                "and remaining dates are half 2."
            )
            or inference.get("test") != "ONE_SIDED_EXACT_BINOMIAL_SIGN_TEST_OF_POSITIVE_MEDIAN_LOG_VARIANCE_RATIO; omit exact-zero ratios from the sign-test denominator."
            or inference.get("raw_symbol_support") != (
                "Both halves meet minimum date sufficiency, both sample medians are strictly positive, "
                "and both one-sided exact sign-test p-values are at most 0.05."
            )
            or inference.get("symbol_family") != (
                "Fixed family of all 41 current structural representatives; insufficient symbols remain in the family with p-value 1."
            )
            or inference.get("multiplicity") != "BENJAMINI_HOCHBERG_FALSE_DISCOVERY_RATE_ACROSS_41_SYMBOLS_USING_LARGER_HALF_P_VALUE_PER_SYMBOL"
            or inference.get("false_discovery_rate") != FDR
            or law.get("no_parameter_search") is not True
            or law.get("prior_epoch_results_are_not_inputs") is not True
            or law.get("internal_development_data_is_not_independent_confirmation") is not True):
        raise Epoch35ScreenError("fixed Epoch35 event or inference law mismatch")
    if freeze.get("accounting_effect") != {
        "economic_outcomes_opened": 0, "v2_attempts_consumed": 0, "search_budget_change": 0,
    }:
        raise Epoch35ScreenError("Epoch35 economic accounting boundary violated")
    interpretation = freeze.get("interpretation_boundary") or {}
    safety = freeze.get("safety") or {}
    if (interpretation.get("economic_promotion_authorized") is not False
            or interpretation.get("mechanism_family_closed") is not False
            or interpretation.get("protected_forward_opened") is not False
            or interpretation.get("independent_confirmation") is not False
            or interpretation.get("winner_selected") is not False
            or interpretation.get("candidate_identity_created") is not False
            or safety.get("protected_forward_opened") is not False
            or safety.get("live_orders_authorized") is not False
            or safety.get("competition_start_authorized") is not False):
        raise Epoch35ScreenError("Epoch35 safety or interpretation boundary violated")
    return registry


def _parse_rows(raw: bytes, member: str, interval: dict[str, str]) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if reader.fieldnames != CSV_FIELDS:
        raise Epoch35ScreenError(f"{member}: unexpected M5 CSV header")
    start = _parse_utc(interval["start_utc"])
    end = _parse_utc(interval["end_utc"])
    rows = []
    for source in reader:
        timestamp = _parse_utc(source["time_utc"])
        try:
            values = {field: float(source[field]) for field in CSV_FIELDS[1:]}
        except (TypeError, ValueError) as exc:
            raise Epoch35ScreenError(f"{member}: invalid numeric field") from exc
        if (not all(math.isfinite(value) for value in values.values())
                or min(values[field] for field in ("open", "high", "low", "close")) <= 0
                or values["tick_volume"] < 0
                or values["high"] < max(values["open"], values["close"], values["low"])
                or values["low"] > min(values["open"], values["close"], values["high"])
                or timestamp < start or timestamp > end):
            raise Epoch35ScreenError(f"{member}: invalid or out-of-scope market row")
        rows.append({"time_utc": source["time_utc"], "timestamp": timestamp, **values})
    if not rows:
        raise Epoch35ScreenError(f"{member}: empty series")
    return rows


def _canonicalize(rows: list[dict[str, Any]], symbol: str) -> tuple[list[dict[str, Any]], int]:
    found: dict[datetime, dict[str, Any]] = {}
    duplicates = 0
    for row in rows:
        timestamp = row["timestamp"]
        previous = found.get(timestamp)
        if previous is None:
            found[timestamp] = row
        elif any(previous[field] != row[field] for field in CSV_FIELDS[1:]):
            raise Epoch35ScreenError(f"{symbol}: conflicting duplicate timestamp {row['time_utc']}")
        else:
            duplicates += 1
    return [found[timestamp] for timestamp in sorted(found)], duplicates


def _contiguous(rows: list[dict[str, Any]], first: int, last: int) -> bool:
    return first >= 0 and last < len(rows) and all(
        (rows[index]["timestamp"] - rows[index - 1]["timestamp"]).total_seconds() == M5_SECONDS
        for index in range(first + 1, last + 1)
    )


def _realized_variance(rows: list[dict[str, Any]], first_close: int, last_close: int) -> float:
    returns = [
        math.log(rows[index]["close"] / rows[index - 1]["close"])
        for index in range(first_close + 1, last_close + 1)
    ]
    return math.fsum(value * value for value in returns)


def _exact_positive_sign_p(values: list[float]) -> float:
    nonzero = [value for value in values if value != 0.0]
    if not nonzero:
        return 1.0
    positives = sum(value > 0.0 for value in nonzero)
    n = len(nonzero)
    return math.fsum(math.comb(n, count) for count in range(positives, n + 1)) / (2 ** n)


def _split_inference(daily: dict[str, float]) -> tuple[list[dict[str, Any]], bool]:
    dates = sorted(daily)
    midpoint = len(dates) // 2
    halves = (dates[:midpoint], dates[midpoint:])
    reports = []
    sufficient = True
    for label, selected in zip(("CHRONOLOGICAL_HALF_1", "CHRONOLOGICAL_HALF_2"), halves):
        values = [daily[day] for day in selected]
        eligible = len(values) >= MIN_DATES_PER_HALF
        sufficient = sufficient and eligible
        reports.append({
            "label": label,
            "eligible_dates": len(values),
            "minimum_dates_pass": eligible,
            "median_log_variance_ratio": statistics.median(values) if values else None,
            "positive_median": bool(values) and statistics.median(values) > 0.0,
            "one_sided_exact_sign_p": _exact_positive_sign_p(values) if eligible else 1.0,
            "positive_signs": sum(value > 0.0 for value in values),
            "negative_signs": sum(value < 0.0 for value in values),
            "zero_signs": sum(value == 0.0 for value in values),
        })
    return reports, sufficient


def _screen_rows(rows: list[dict[str, Any]], broker_symbol: str, symbol_id: int) -> dict[str, Any]:
    daily: dict[str, float] = {}
    excluded = {
        "incomplete_or_noncontiguous_outcome_window": 0,
        "nonpositive_realized_variance": 0,
        "duplicate_utc_date_event": 0,
    }
    event_candidates = 0
    for index in range(LOOKBACK_BARS, len(rows)):
        prior = rows[index - LOOKBACK_BARS:index]
        current = rows[index]
        if len(prior) != LOOKBACK_BARS or not _contiguous(rows, index - LOOKBACK_BARS, index):
            continue
        prior_median_range = statistics.median(bar["high"] - bar["low"] for bar in prior)
        current_range = current["high"] - current["low"]
        if current_range <= 0.0 or current_range < 2.0 * prior_median_range:
            continue
        event_candidates += 1
        event_day = current["timestamp"].date().isoformat()
        if not _contiguous(rows, index - HORIZON_BARS, index + HORIZON_BARS):
            excluded["incomplete_or_noncontiguous_outcome_window"] += 1
            continue
        baseline_rv = _realized_variance(rows, index - HORIZON_BARS, index)
        forward_rv = _realized_variance(rows, index, index + HORIZON_BARS)
        if baseline_rv <= 0.0 or forward_rv <= 0.0:
            excluded["nonpositive_realized_variance"] += 1
            continue
        if event_day in daily:
            excluded["duplicate_utc_date_event"] += 1
            continue
        daily[event_day] = math.log(forward_rv / baseline_rv)

    halves, sufficient = _split_inference(daily)
    max_half_p = max((report["one_sided_exact_sign_p"] for report in halves), default=1.0)
    raw_support = sufficient and all(
        report["positive_median"] and report["one_sided_exact_sign_p"] <= FDR
        for report in halves
    )
    return {
        "symbol_id": symbol_id,
        "rows": len(rows),
        "event_candidates": event_candidates,
        "eligible_events": len(daily),
        "eligible_utc_dates": sorted(daily),
        "daily_log_variance_ratios": dict(sorted(daily.items())),
        "excluded_events": excluded,
        "chronological_half_1": halves[0],
        "chronological_half_2": halves[1],
        "minimum_data_sufficiency_pass": sufficient,
        "max_half_p_value": max_half_p,
        "raw_positive_median_pass": raw_support,
    }


def benjamini_hochberg(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    count = len(ordered)
    adjusted: dict[str, float] = {}
    running = 1.0
    for index in range(count - 1, -1, -1):
        symbol, value = ordered[index]
        running = min(running, value * count / (index + 1), 1.0)
        adjusted[symbol] = running
    return adjusted


def _load_archive(
    archive: zipfile.ZipFile, expected: dict[int, str], interval: dict[str, str],
    allowed_superseded_ids: set[int] | None = None,
) -> dict[int, list[dict[str, Any]]]:
    try:
        manifest = json.loads(archive.read("capture_manifest.json"))
    except (KeyError, json.JSONDecodeError) as exc:
        raise Epoch35ScreenError("top-level capture_manifest.json missing or invalid") from exc
    if not isinstance(manifest, dict):
        raise Epoch35ScreenError("capture manifest must be a JSON object")
    if (manifest.get("resolution") != "M5"
            or manifest.get("protected_evidence_opened") is not False
            or manifest.get("economic_outcomes_opened") != 0):
        raise Epoch35ScreenError("capture manifest violates resolution or safety requirements")
    series = manifest.get("series")
    if not isinstance(series, list) or any(not isinstance(item, dict) for item in series):
        raise Epoch35ScreenError("capture manifest series must be a list of objects")
    complete_all = [
        item for item in series
        if item.get("capture_status") == "SERIES_CAPTURE_COMPLETE"
    ]
    allowed_superseded_ids = allowed_superseded_ids or set()
    try:
        extra_ids = {int(item["symbol_id"]) for item in complete_all} - set(expected)
    except (KeyError, ValueError, TypeError) as exc:
        raise Epoch35ScreenError("capture manifest series identity is incomplete") from exc
    if extra_ids != allowed_superseded_ids or len(complete_all) != len(expected) + len(extra_ids):
        raise Epoch35ScreenError("capture contains unexpected or duplicate complete series")
    complete = [item for item in complete_all if int(item["symbol_id"]) in expected]
    if len(complete) != len(expected):
        raise Epoch35ScreenError(f"expected {len(expected)} complete series, observed {len(complete)}")
    result: dict[int, list[dict[str, Any]]] = {}
    seen_members: set[str] = set()
    for item in complete:
        try:
            symbol_id = int(item["symbol_id"])
            symbol = str(item["broker_symbol"])
            member = str(item["file"])
        except (KeyError, TypeError, ValueError) as exc:
            raise Epoch35ScreenError("capture manifest series identity is incomplete") from exc
        if (symbol_id not in expected or expected[symbol_id] != symbol or symbol_id in result
                or member in seen_members
                or not member.startswith(f"raw/{symbol_id}_") or not member.endswith("_M5.csv")
                or item.get("synthetic_fill") is not False or item.get("forward_fill") is not False):
            raise Epoch35ScreenError(f"unexpected, duplicate, or filled capture series: {symbol}/{symbol_id}")
        seen_members.add(member)
        try:
            raw = archive.read(member)
        except KeyError as exc:
            raise Epoch35ScreenError(f"{symbol}: declared capture member missing") from exc
        if _sha256_bytes(raw) != item.get("sha256"):
            raise Epoch35ScreenError(f"{symbol}: manifest member hash mismatch")
        rows = _parse_rows(raw, member, interval)
        if len(rows) != item.get("row_count"):
            raise Epoch35ScreenError(f"{symbol}: manifest row count mismatch")
        rows, _ = _canonicalize(rows, symbol)
        result[symbol_id] = rows
    if set(result) != set(expected):
        raise Epoch35ScreenError("capture does not contain the exact required representative IDs")
    return result

def _load_replacement_archive(
    archive: zipfile.ZipFile, expected: dict[int, str], interval: dict[str, str],
) -> dict[int, list[dict[str, Any]]]:
    """Read the accepted replacement transport format with its root checksum ledger."""
    manifest_raw=archive.read("capture_manifest.json")
    manifest=json.loads(manifest_raw)
    if (manifest.get("completion_state")!="COMPLETE"
            or manifest.get("protected_evidence_opened") is not False
            or manifest.get("economic_outcomes_opened")!=0
            or manifest.get("account_mutation") is not False):
        raise Epoch35ScreenError("replacement capture safety or completion mismatch")
    checks={}
    for line in archive.read("CHECKSUMS.sha256").decode("utf-8").splitlines():
        digest,member=line.split(None,1)
        checks[member.strip()]=digest
    if checks.get("capture_manifest.json")!=_sha256_bytes(manifest_raw):
        raise Epoch35ScreenError("replacement manifest checksum mismatch")
    members=[name for name in archive.namelist() if name.startswith("raw/") and name.endswith("_M5.csv")]
    if len(members)!=len(expected) or set(checks)!={"capture_manifest.json",*members}:
        raise Epoch35ScreenError("replacement archive has unexpected canonical members")
    result={}
    for symbol_id,symbol in expected.items():
        matches=[name for name in members if name.startswith(f"raw/{symbol_id}_")]
        if len(matches)!=1:
            raise Epoch35ScreenError(f"replacement identity missing or duplicated: {symbol_id}")
        raw=archive.read(matches[0])
        if _sha256_bytes(raw)!=checks[matches[0]]:
            raise Epoch35ScreenError(f"replacement member checksum mismatch: {symbol_id}")
        result[symbol_id]=_canonicalize(_parse_rows(raw,matches[0],interval),symbol)[0]
    return result


def evaluate(
    freeze: dict[str, Any], development_zip: Path, replacement_zip: Path, root: Path,
) -> dict[str, Any]:
    registry = validate_freeze(freeze, root)
    if (sha256_file(development_zip) != DEVELOPMENT_SHA256
            or sha256_file(replacement_zip) != REPLACEMENT_SHA256):
        raise Epoch35ScreenError("accepted capture ZIP hash mismatch")
    representatives = registry["representatives"]
    by_id = {int(item["symbol_id"]): str(item["broker_symbol"]) for item in representatives}
    development_ids = set(by_id) - REPLACEMENT_IDS
    if len(development_ids) != 38 or len(REPLACEMENT_IDS) != 3:
        raise Epoch35ScreenError("frozen archive split does not cover exactly 41 representatives")
    interval = freeze["scope"]["interval"]
    with zipfile.ZipFile(development_zip) as development, zipfile.ZipFile(replacement_zip) as replacement:
        development_rows = _load_archive(
            development, {symbol_id: by_id[symbol_id] for symbol_id in development_ids}, interval,
            allowed_superseded_ids=SUPERSEDED_DEVELOPMENT_IDS,
        )
        replacement_rows = _load_replacement_archive(
            replacement, {symbol_id: by_id[symbol_id] for symbol_id in REPLACEMENT_IDS}, interval,
        )
    all_rows = {**development_rows, **replacement_rows}
    if set(all_rows) != set(by_id):
        raise Epoch35ScreenError("Epoch35 did not load all current representatives")
    per_symbol: dict[str, Any] = {}
    for item in representatives:
        symbol_id = int(item["symbol_id"])
        symbol = str(item["broker_symbol"])
        result = _screen_rows(all_rows[symbol_id], symbol, symbol_id)
        result["supported_after_bh_fdr"] = False
        per_symbol[symbol] = result
    if len(per_symbol) != 41:
        raise Epoch35ScreenError("Epoch35 did not process the full 41-symbol panel exactly once")
    adjusted = benjamini_hochberg({
        symbol: result["max_half_p_value"] for symbol, result in per_symbol.items()
    })
    for symbol, result in per_symbol.items():
        result["bh_adjusted_p"] = adjusted[symbol]
        result["supported_after_bh_fdr"] = (
            result["raw_positive_median_pass"] and adjusted[symbol] <= FDR
        )
    return {
        "schema": "mxm.greenfield.epoch35-breakout-unsigned-volatility-structural-result.v1",
        "status": "COMPLETE_NON_ECONOMIC_STRUCTURAL_RESULT",
        "evidence_epoch": 35,
        "family": "BREAKOUT_VOLATILITY_EXPANSION",
        "freeze_ref": FREEZE_REF,
        "implementation": {"version": VERSION},
        "scope": {
            "representatives_processed": len(per_symbol),
            "all_41_processed_exactly_once": len(per_symbol) == 41,
            "representatives_are_economic_equivalents": False,
            "resolution": "M5",
        },
        "input_attestation": {
            "proposal_file_sha256": sha256_file(root / PROPOSAL_REF),
            "current_frontier_sha256": sha256_file(root / CURRENT_FRONTIER_REF),
            "registry_sha256": sha256_file(root / REGISTRY_REF),
            "coverage_sha256": sha256_file(root / COVERAGE_REF),
            "development_zip_sha256": sha256_file(development_zip),
            "replacement_zip_sha256": sha256_file(replacement_zip),
            "protected_forward_rows_read": 0,
            "prior_epoch_screen_results_used_as_inputs": False,
            "new_market_data_acquired": False,
        },
        "inference": {
            "eligible_symbols": sum(result["minimum_data_sufficiency_pass"] for result in per_symbol.values()),
            "supported_symbols_after_bh_fdr": sum(result["supported_after_bh_fdr"] for result in per_symbol.values()),
            "family_size": 41,
            "method": "ONE_SIDED_EXACT_SIGN_TEST_BY_CHRONOLOGICAL_HALF_WITH_BH_FDR",
            "false_discovery_rate": FDR,
        },
        "symbols": per_symbol,
        "interpretation_boundary": {
            "unsigned_volatility_structure_only": True,
            "independent_confirmation": False,
            "economic_promotion_authorized": False,
            "mechanism_family_closed": False,
            "winner_selected": False,
            "candidate_identity_created": False,
            "protected_forward_opened": False,
            "internal_development_data_is_independent_confirmation": False,
        },
        "accounting_effect": {
            "economic_outcomes_opened": 0,
            "v2_attempts_consumed": 0,
            "search_budget_change": 0,
        },
        "safety": {
            "protected_forward_opened": False,
            "live_orders_authorized": False,
            "competition_start_authorized": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=VERSION)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--development-zip", type=Path)
    parser.add_argument("--replacement-zip", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    development_zip = args.development_zip or root / "research_v3/runtime_v2_inputs/MXM_BROKER_NATIVE_FRONTIER_M5_13W_DEVELOPMENT_V1.zip"
    replacement_zip = args.replacement_zip or root / "research_v3/runtime_v2_inputs/MXM_CURRENT_FRONTIER_REPLACEMENT_13W_M5_V1.zip"
    freeze = _load_json(root / FREEZE_REF)
    result = evaluate(freeze, development_zip, replacement_zip, root)
    output = args.output or root / RESULT_REF
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "result_ref": str(output), "symbols": 41}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
