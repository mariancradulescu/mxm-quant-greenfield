from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

VERSION = "MXM_EPOCH24_TREND_MOMENTUM_STRUCTURAL_SCREEN_V1"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_utc(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def sign(value: float) -> int:
    return 1 if value > 0 else (-1 if value < 0 else 0)


def exact_binomial_greater(k: int, n: int) -> float:
    if n < 0 or k < 0 or k > n:
        raise ValueError("invalid binomial counts")
    if n == 0:
        return 1.0
    return sum(math.comb(n, i) for i in range(k, n + 1)) / (2 ** n)


def bh_adjust(p_values: dict[str, float]) -> dict[str, float]:
    items = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    m = len(items)
    adjusted: dict[str, float] = {}
    running = 1.0
    for rank in range(m, 0, -1):
        key, p_value = items[rank - 1]
        running = min(running, min(1.0, p_value * m / rank))
        adjusted[key] = running
    return adjusted


def canonicalize_identical_duplicates(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    by_timestamp: dict[datetime, dict[str, Any]] = {}
    duplicates = 0
    for row in rows:
        timestamp = row["timestamp"]
        previous = by_timestamp.get(timestamp)
        if previous is None:
            by_timestamp[timestamp] = row
            continue
        for field in ("open", "high", "low", "close", "tick_volume"):
            if previous[field] != row[field]:
                raise ValueError(f"conflicting duplicate at {row['time_utc']}")
        duplicates += 1
    return [by_timestamp[key] for key in sorted(by_timestamp)], duplicates


def split_contiguous(rows: list[dict[str, Any]], seconds: int = 300) -> list[list[dict[str, Any]]]:
    if not rows:
        return []
    segments = [[rows[0]]]
    for row in rows[1:]:
        delta = (row["timestamp"] - segments[-1][-1]["timestamp"]).total_seconds()
        if delta == seconds:
            segments[-1].append(row)
        elif delta > 0:
            segments.append([row])
        else:
            raise ValueError("rows not strictly chronological after canonicalization")
    return segments


def evaluate_symbol(rows: list[dict[str, Any]], *, lookback: int = 12, response: int = 12, stride: int = 12) -> dict[str, Any]:
    rows, duplicates_removed = canonicalize_identical_duplicates(rows)
    segments = split_contiguous(rows)
    admitted: list[dict[str, Any]] = []
    for segment_index, segment in enumerate(segments):
        for index in range(lookback, len(segment), stride):
            past_direction = sign(segment[index]["close"] - segment[index - lookback]["close"])
            record = {
                "timestamp": segment[index]["timestamp"],
                "segment_index": segment_index,
                "past_direction": past_direction,
                "settled": False,
                "response_direction": None,
                "classification": "RIGHT_CENSORED_FUTURE_RESPONSE",
            }
            if index + response < len(segment):
                response_direction = sign(segment[index + response]["close"] - segment[index]["close"])
                record["settled"] = True
                record["response_direction"] = response_direction
                if past_direction == 0 or response_direction == 0:
                    record["classification"] = "ZERO_DIRECTION"
                elif past_direction == response_direction:
                    record["classification"] = "CONTINUATION"
                else:
                    record["classification"] = "REVERSAL"
            admitted.append(record)

    settled = [row for row in admitted if row["settled"]]
    both = [
        row for row in settled
        if row["past_direction"] != 0 and row["response_direction"] != 0
    ]
    both.sort(key=lambda row: row["timestamp"])
    split_index = len(both) // 2
    halves = [both[:split_index], both[split_index:]]
    continuation = sum(row["classification"] == "CONTINUATION" for row in both)
    reversal = sum(row["classification"] == "REVERSAL" for row in both)
    half_counts = []
    for half in halves:
        cont = sum(row["classification"] == "CONTINUATION" for row in half)
        rev = sum(row["classification"] == "REVERSAL" for row in half)
        half_counts.append({
            "both_nonzero_settled": len(half),
            "continuation": cont,
            "reversal": rev,
            "continuation_fraction": cont / len(half) if half else None,
        })
    return {
        "rows": len(rows),
        "identical_duplicate_rows_removed": duplicates_removed,
        "contiguous_segments": len(segments),
        "admitted_anchors": len(admitted),
        "right_censored_future_response": sum(not row["settled"] for row in admitted),
        "settled_anchors": len(settled),
        "zero_direction_settled": sum(row["classification"] == "ZERO_DIRECTION" for row in settled),
        "both_nonzero_settled": len(both),
        "continuation": continuation,
        "reversal": reversal,
        "continuation_fraction": continuation / len(both) if both else None,
        "one_sided_exact_binomial_p": exact_binomial_greater(continuation, len(both)),
        "chronological_half_1": half_counts[0],
        "chronological_half_2": half_counts[1],
    }


def _read_member(zf: zipfile.ZipFile, member: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(zf.read(member).decode("utf-8-sig").splitlines())
    rows = []
    for row in reader:
        rows.append({
            "time_utc": row["time_utc"],
            "timestamp": parse_utc(row["time_utc"]),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "tick_volume": float(row.get("tick_volume") or 0),
        })
    return rows


def _find_member(zf: zipfile.ZipFile, symbol_id: int) -> str:
    prefix = f"raw/{symbol_id}_"
    matches = [name for name in zf.namelist() if name.startswith(prefix) and name.endswith("_M5.csv")]
    if len(matches) != 1:
        raise ValueError(f"expected one root raw M5 member for symbol_id={symbol_id}, got {matches}")
    return matches[0]


def evaluate(freeze: dict[str, Any], development_zip: Path, replacement_zip: Path) -> dict[str, Any]:
    law = freeze["preregistered_structural_law"]
    if law["resolution"] != "M5":
        raise ValueError("unsupported resolution")
    replacement_ids = {2924, 5352, 7427}
    results: dict[str, Any] = {}
    with zipfile.ZipFile(development_zip) as development, zipfile.ZipFile(replacement_zip) as replacement:
        for representative in freeze["scope"]["representatives"]:
            symbol_id = int(representative["symbol_id"])
            symbol = representative["broker_symbol"]
            source = replacement if symbol_id in replacement_ids else development
            member = _find_member(source, symbol_id)
            results[symbol] = {
                "symbol_id": symbol_id,
                "source_member": member,
                **evaluate_symbol(
                    _read_member(source, member),
                    lookback=int(law["lookback_bars"]),
                    response=int(law["response_bars"]),
                    stride=int(law["anchor_stride_bars"]),
                ),
            }

    adjusted = bh_adjust({symbol: row["one_sided_exact_binomial_p"] for symbol, row in results.items()})
    q_limit = float(law["inference"]["fdr_q"])
    minimum_half = int(law["inference"]["minimum_both_nonzero_settled_per_chronological_half"])
    supported = []
    for symbol, row in results.items():
        row["bh_adjusted_q"] = adjusted[symbol]
        half1 = row["chronological_half_1"]
        half2 = row["chronological_half_2"]
        row["stability_pass"] = (
            row["continuation_fraction"] is not None and row["continuation_fraction"] > 0.5
            and half1["continuation_fraction"] is not None and half1["continuation_fraction"] > 0.5
            and half2["continuation_fraction"] is not None and half2["continuation_fraction"] > 0.5
        )
        row["minimum_half_observations_pass"] = (
            half1["both_nonzero_settled"] >= minimum_half
            and half2["both_nonzero_settled"] >= minimum_half
        )
        row["supported_symbol"] = (
            row["bh_adjusted_q"] <= q_limit
            and row["stability_pass"]
            and row["minimum_half_observations_pass"]
        )
        if row["supported_symbol"]:
            supported.append(symbol)

    return {
        "schema": "mxm.greenfield.epoch24-trend-momentum-structural-result.v1",
        "status": "COMPLETE_NON_ECONOMIC_STRUCTURAL_RESULT",
        "evidence_epoch": 24,
        "family": "TREND_MOMENTUM",
        "freeze_ref": "research_v3/EPOCH24_TREND_MOMENTUM_FRONTIER_FREEZE_V1.json",
        "implementation": {
            "version": VERSION,
            "chronological_half_operationalization": (
                "Per symbol, sort settled both-nonzero anchors by anchor timestamp; "
                "half 1 is the first floor(N/2), half 2 is the remaining anchors. "
                "This operational clarification is fixed before inspecting per-symbol outcomes."
            ),
        },
        "source_artifacts": {
            "development_zip_sha256": sha256_file(development_zip),
            "replacement_zip_sha256": sha256_file(replacement_zip),
        },
        "scope": {
            "representatives": len(results),
            "all_frozen_representatives_processed_exactly_once": (
                len(results) == int(freeze["scope"]["representative_count"])
            ),
            "consumed_prior_trend_overlap": sorted(
                set(results) & set(freeze["scope"]["consumed_prior_trend_symbols"])
            ),
        },
        "inference": {
            "fdr_q": q_limit,
            "minimum_both_nonzero_settled_per_chronological_half": minimum_half,
            "supported_symbols_count": len(supported),
            "supported_symbols": sorted(supported),
        },
        "symbols": results,
        "aggregate": {
            "admitted_anchors": sum(row["admitted_anchors"] for row in results.values()),
            "settled_anchors": sum(row["settled_anchors"] for row in results.values()),
            "both_nonzero_settled": sum(row["both_nonzero_settled"] for row in results.values()),
            "continuation": sum(row["continuation"] for row in results.values()),
            "reversal": sum(row["reversal"] for row in results.values()),
            "right_censored_future_response": sum(
                row["right_censored_future_response"] for row in results.values()
            ),
        },
        "accounting_effect": {
            "v2_attempts_consumed": 0,
            "economic_outcomes_opened": 0,
            "search_budget_change": 0,
        },
        "safety": {
            "protected_forward_opened": False,
            "live_orders_authorized": False,
            "account_mutation": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=VERSION)
    parser.add_argument("--freeze", required=True)
    parser.add_argument("--development-zip", required=True)
    parser.add_argument("--replacement-zip", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    freeze = json.loads(Path(args.freeze).read_text(encoding="utf-8"))
    result = evaluate(freeze, Path(args.development_zip), Path(args.replacement_zip))
    Path(args.output).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": result["status"],
        "supported_symbols_count": result["inference"]["supported_symbols_count"],
        "supported_symbols": result["inference"]["supported_symbols"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
