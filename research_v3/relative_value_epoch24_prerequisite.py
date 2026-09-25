"""Outcome-blind relative-value data alignment audit for the accepted epoch-23 frontier.

This module preserves the already-accepted timestamp inventory and adds a reusable,
hash-bound synchronized close-price builder for the next non-economic relative-value
diagnostic phase. It never fits a hedge, tests cointegration, computes returns/PnL,
or selects a winning pair.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from decimal import Decimal, InvalidOperation
from itertools import combinations
from pathlib import Path
from typing import Any, Mapping
from zipfile import ZipFile

OLD_ZIP_SHA256 = "64ea52126a31c527d2021a50923adab1b7df8f0ce5debe7f631cf4ce09b39503"
REPLACEMENT_ZIP_SHA256 = "d9be18c7aa902a83bad0417bc561b7ef8df4c3ac357ff884d98c4ee3e0cc5d75"
REPLACEMENTS = {"CXMT.CN-PERP", "ERICB.SE", "XAUUSD-F"}
ALIGNMENT_INVENTORY_REF = "evidence/EPOCH24_RELATIVE_VALUE_ALIGNMENT_PREREQUISITE_V1.json"
AMBIGUOUS_PRODUCT_TYPES = {"", "OTHER_OR_TEST_CFD", "UNKNOWN", "UNCLASSIFIED"}


class PairDataError(ValueError):
    """Fail-closed error for synchronized relative-value input construction."""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _timestamp_set_sha256(values) -> str:
    payload = ("\n".join(sorted(values)) + "\n").encode("utf-8")
    return sha(payload)


def _parse_positive_decimal(value: str, *, symbol: str, timestamp: str) -> Decimal:
    if value is None or not str(value).strip():
        raise PairDataError(f"missing close for {symbol} at {timestamp}")
    try:
        out = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise PairDataError(f"invalid close for {symbol} at {timestamp}") from exc
    if not out.is_finite() or out <= 0:
        raise PairDataError(f"non-positive/non-finite close for {symbol} at {timestamp}")
    return out


def read_price_series_bytes(
    raw: bytes,
    expected_raw_hash: str,
    *,
    broker_symbol: str,
    symbol_id: int,
    canonicalize: bool,
) -> dict[str, Any]:
    """Read one hash-bound M5 close series without interpolation or outcome transforms."""
    if sha(raw) != expected_raw_hash:
        raise PairDataError(f"raw series hash mismatch: {broker_symbol}")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    required = {"time_utc", "close"}
    if not required.issubset(set(reader.fieldnames or [])):
        raise PairDataError(f"required columns missing for {broker_symbol}: {sorted(required)}")

    rows: dict[str, dict[str, str]] = {}
    closes: dict[str, Decimal] = {}
    duplicates = 0
    ordered: list[str] = []
    for row in reader:
        timestamp = str(row.get("time_utc") or "").strip()
        if not timestamp:
            raise PairDataError(f"missing time_utc for {broker_symbol}")
        if timestamp in rows:
            if rows[timestamp] != row:
                raise PairDataError(f"conflicting duplicate at {broker_symbol} {timestamp}")
            duplicates += 1
            if not canonicalize:
                raise PairDataError(f"unexpected duplicate in accepted original series: {broker_symbol}")
            continue
        rows[timestamp] = row
        closes[timestamp] = _parse_positive_decimal(
            row.get("close"), symbol=broker_symbol, timestamp=timestamp
        )
        ordered.append(timestamp)

    if not ordered:
        raise PairDataError(f"empty series: {broker_symbol}")
    if ordered != sorted(ordered) and not canonicalize:
        raise PairDataError(f"out-of-order timestamps: {broker_symbol}")

    ordered = sorted(closes)
    return {
        "broker_symbol": broker_symbol,
        "symbol_id": int(symbol_id),
        "raw_sha256": expected_raw_hash,
        "rows": len(ordered),
        "identical_duplicate_rows_removed": duplicates,
        "timestamps": tuple(ordered),
        "closes": {ts: closes[ts] for ts in ordered},
    }


def read_series(z: ZipFile, path: str, expected_raw_hash: str, *, canonicalize: bool):
    """Compatibility wrapper retained for the accepted alignment inventory audit."""
    raw = z.read(path)
    if sha(raw) != expected_raw_hash:
        raise ValueError(f"raw series hash mismatch: {path}")
    seen = {}
    duplicates = 0
    for row in csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))):
        ts = row["time_utc"]
        if ts in seen:
            if seen[ts] != row:
                raise ValueError(f"conflicting duplicate at {path} {ts}")
            duplicates += 1
        else:
            seen[ts] = row
    if duplicates and not canonicalize:
        raise ValueError(f"unexpected duplicate in accepted original series: {path}")
    ordered = list(seen)
    if ordered != sorted(ordered) and not canonicalize:
        raise ValueError(f"out-of-order timestamps: {path}")
    return set(ordered), duplicates


def _registry_index(registry: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    reps = list(registry.get("representatives") or [])
    by_symbol = {str(r.get("broker_symbol")): r for r in reps}
    if len(reps) != 41 or len(by_symbol) != 41:
        raise PairDataError(
            "current structural frontier differs from accepted 41-representative authority"
        )
    for symbol, rep in by_symbol.items():
        if rep.get("symbol_id") is None or not rep.get("signature"):
            raise PairDataError(f"incomplete registry identity: {symbol}")
    return by_symbol


def validate_alignment_inventory(inventory: Mapping[str, Any]) -> None:
    accepted = inventory.get("accepted_inputs") or {}
    if inventory.get("status") != "COMPLETE_NON_ECONOMIC_ALIGNMENT_INVENTORY_NO_PAIR_SELECTED":
        raise PairDataError("alignment inventory status is not accepted")
    if accepted.get("original_zip_sha256") != OLD_ZIP_SHA256:
        raise PairDataError("alignment inventory original capture hash mismatch")
    if accepted.get("replacement_zip_sha256") != REPLACEMENT_ZIP_SHA256:
        raise PairDataError("alignment inventory replacement capture hash mismatch")
    if int(inventory.get("pair_count") or -1) != 820:
        raise PairDataError("alignment inventory pair count mismatch")
    if len(inventory.get("pairs") or []) != 820:
        raise PairDataError("alignment inventory pair list is incomplete")


def build_accepted_price_series(
    old_zip: Path,
    replacement_zip: Path,
    registry: Mapping[str, Any],
    acceptance: Mapping[str, Any],
    *,
    alignment_inventory: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build hash-bound accepted close series while preserving the durable inventory authority."""
    if sha(old_zip.read_bytes()) != OLD_ZIP_SHA256:
        raise PairDataError("original capture transport identity does not match accepted evidence")
    if sha(replacement_zip.read_bytes()) != REPLACEMENT_ZIP_SHA256:
        raise PairDataError("replacement capture transport identity does not match accepted evidence")
    if alignment_inventory is not None:
        validate_alignment_inventory(alignment_inventory)

    by_symbol = _registry_index(registry)
    if set(acceptance.get("series") or {}) != REPLACEMENTS:
        raise PairDataError("replacement acceptance differs from accepted epoch-23 authority")

    output: dict[str, dict[str, Any]] = {}
    with ZipFile(old_zip) as old, ZipFile(replacement_zip) as replacement:
        if old.testzip() or replacement.testzip():
            raise PairDataError("zip CRC failure")
        manifest = json.loads(old.read("capture_manifest.json"))
        old_series = {s["broker_symbol"]: s for s in manifest["series"]}
        for symbol, rep in sorted(by_symbol.items()):
            if symbol in REPLACEMENTS:
                bound = acceptance["series"][symbol]
                if int(bound["symbol_id"]) != int(rep["symbol_id"]):
                    raise PairDataError(f"replacement identity mismatch: {symbol}")
                raw = replacement.read(bound["raw_path"])
                series = read_price_series_bytes(
                    raw,
                    bound["raw_sha256"],
                    broker_symbol=symbol,
                    symbol_id=rep["symbol_id"],
                    canonicalize=True,
                )
                if (
                    series["rows"] != int(bound["canonical_rows"])
                    or series["identical_duplicate_rows_removed"]
                    != int(bound["identical_duplicate_rows_removed"])
                ):
                    raise PairDataError(f"replacement canonicalization mismatch: {symbol}")
                series["source"] = "EPOCH23_REPLACEMENT"
            else:
                bound = old_series.get(symbol)
                if bound is None:
                    raise PairDataError(f"accepted original series missing: {symbol}")
                if int(bound["symbol_id"]) != int(rep["symbol_id"]):
                    raise PairDataError(f"original identity mismatch: {symbol}")
                raw = old.read(bound["file"])
                series = read_price_series_bytes(
                    raw,
                    bound["sha256"],
                    broker_symbol=symbol,
                    symbol_id=rep["symbol_id"],
                    canonicalize=False,
                )
                if series["rows"] != int(bound["row_count"]):
                    raise PairDataError(f"original row count mismatch: {symbol}")
                series["source"] = "ACCEPTED_13W_DEVELOPMENT"
            output[symbol] = series
    return output


def _explicit_quote_unit(
    authority: Mapping[str, Any] | None, symbol: str
) -> tuple[str | None, str | None]:
    if not authority or symbol not in authority:
        return None, None
    value = authority[symbol]
    if isinstance(value, str):
        unit = value.strip().upper()
        return (unit or None), "CALLER_EXPLICIT"
    if isinstance(value, Mapping):
        unit = str(value.get("quote_unit") or "").strip().upper()
        source = (
            str(value.get("source_ref") or value.get("source") or "").strip()
            or "CALLER_EXPLICIT"
        )
        return (unit or None), source
    raise PairDataError(f"invalid quote-unit authority entry for {symbol}")


def product_quote_comparability(
    left_rep: Mapping[str, Any],
    right_rep: Mapping[str, Any],
    *,
    quote_unit_authority: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Conservative comparability gate; quote units are never inferred from symbol names."""
    left_symbol = str(left_rep["broker_symbol"])
    right_symbol = str(right_rep["broker_symbol"])
    left_sig = list(left_rep.get("signature") or [])
    right_sig = list(right_rep.get("signature") or [])
    if len(left_sig) < 2 or len(right_sig) < 2:
        raise PairDataError("structural signature missing product metadata")

    left_asset, right_asset = str(left_sig[0]), str(right_sig[0])
    left_product, right_product = str(left_sig[1]), str(right_sig[1])
    same_asset_class = left_asset == right_asset
    same_product_type = left_product == right_product
    product_unambiguous = (
        left_product not in AMBIGUOUS_PRODUCT_TYPES
        and right_product not in AMBIGUOUS_PRODUCT_TYPES
    )
    left_quote, left_quote_source = _explicit_quote_unit(quote_unit_authority, left_symbol)
    right_quote, right_quote_source = _explicit_quote_unit(quote_unit_authority, right_symbol)
    quote_units_explicit = left_quote is not None and right_quote is not None
    same_quote_unit = quote_units_explicit and left_quote == right_quote

    reasons = []
    if not same_asset_class:
        reasons.append("ASSET_CLASS_MISMATCH")
    if not same_product_type:
        reasons.append("PRODUCT_TYPE_MISMATCH")
    if same_product_type and not product_unambiguous:
        reasons.append("AMBIGUOUS_PRODUCT_TYPE_FAIL_CLOSED")
    if not quote_units_explicit:
        reasons.append("QUOTE_UNIT_UNKNOWN_FAIL_CLOSED")
    elif not same_quote_unit:
        reasons.append("QUOTE_UNIT_MISMATCH")

    comparable = (
        same_asset_class
        and same_product_type
        and product_unambiguous
        and quote_units_explicit
        and same_quote_unit
    )
    return {
        "status": "COMPARABLE" if comparable else "NOT_COMPARABLE_FAIL_CLOSED",
        "comparable": comparable,
        "same_asset_class": same_asset_class,
        "same_product_type": same_product_type,
        "product_type_unambiguous": product_unambiguous,
        "left_product_type": left_product,
        "right_product_type": right_product,
        "quote_units_explicit": quote_units_explicit,
        "same_quote_unit": same_quote_unit,
        "left_quote_unit": left_quote,
        "right_quote_unit": right_quote,
        "left_quote_unit_source": left_quote_source,
        "right_quote_unit_source": right_quote_source,
        "reasons": reasons,
        "quote_unit_inference_from_symbol_name": False,
    }


def synchronize_pair(
    left_series: Mapping[str, Any],
    right_series: Mapping[str, Any],
    left_rep: Mapping[str, Any],
    right_rep: Mapping[str, Any],
    *,
    quote_unit_authority: Mapping[str, Any] | None = None,
    expected_common_m5_timestamps: int | None = None,
) -> dict[str, Any]:
    """Intersect two accepted price series without fill, ranking, or economic transforms."""
    for series, rep, side in (
        (left_series, left_rep, "left"),
        (right_series, right_rep, "right"),
    ):
        if str(series.get("broker_symbol")) != str(rep.get("broker_symbol")):
            raise PairDataError(f"{side} broker-symbol identity mismatch")
        if int(series.get("symbol_id")) != int(rep.get("symbol_id")):
            raise PairDataError(f"{side} symbol-id identity mismatch")

    left_times = set(left_series["timestamps"])
    right_times = set(right_series["timestamps"])
    common = sorted(left_times & right_times)
    left_only = left_times - right_times
    right_only = right_times - left_times
    if expected_common_m5_timestamps is not None and len(common) != int(
        expected_common_m5_timestamps
    ):
        raise PairDataError(
            "synchronized intersection disagrees with accepted alignment inventory"
        )

    aligned = [
        {
            "time_utc": ts,
            "left_close": str(left_series["closes"][ts]),
            "right_close": str(right_series["closes"][ts]),
        }
        for ts in common
    ]
    comparability = product_quote_comparability(
        left_rep, right_rep, quote_unit_authority=quote_unit_authority
    )
    return {
        "schema": "mxm.greenfield.relative-value-synchronized-price-pair.v1",
        "symbols": [left_rep["broker_symbol"], right_rep["broker_symbol"]],
        "symbol_ids": [int(left_rep["symbol_id"]), int(right_rep["symbol_id"])],
        "alignment": {
            "common_m5_timestamps": len(common),
            "left_rows": len(left_times),
            "right_rows": len(right_times),
            "left_only_rows": len(left_only),
            "right_only_rows": len(right_only),
            "left_only_timestamps_sha256": _timestamp_set_sha256(left_only),
            "right_only_timestamps_sha256": _timestamp_set_sha256(right_only),
            "missingness_policy": "EXPLICIT_INTERSECTION_ONLY_NO_FORWARD_FILL_NO_IMPUTATION",
            "forward_filled_rows": 0,
            "imputed_rows": 0,
        },
        "comparability": comparability,
        "synchronized_closes": aligned,
        "economic_effect": {
            "returns_or_pnl_computed": False,
            "hedge_fitted": False,
            "cointegration_tested": False,
            "winning_pair_selected": False,
            "economic_outcomes_opened": 0,
            "v2_attempts_consumed": 0,
            "protected_forward_opened": False,
        },
    }


def prepare_inventory_bound_pair(
    left_symbol: str,
    right_symbol: str,
    series_by_symbol: Mapping[str, Mapping[str, Any]],
    registry: Mapping[str, Any],
    alignment_inventory: Mapping[str, Any],
    *,
    quote_unit_authority: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Prepare exactly one caller-specified pair and bind it to the accepted 820-pair inventory."""
    validate_alignment_inventory(alignment_inventory)
    by_symbol = _registry_index(registry)
    if left_symbol == right_symbol:
        raise PairDataError("pair requires two distinct broker symbols")
    if left_symbol not in by_symbol or right_symbol not in by_symbol:
        raise PairDataError("pair symbol is outside accepted 41-representative authority")
    if left_symbol not in series_by_symbol or right_symbol not in series_by_symbol:
        raise PairDataError("accepted price series missing for requested pair")

    key = tuple(sorted((left_symbol, right_symbol)))
    inventory_pairs = {tuple(p["symbols"]): p for p in alignment_inventory["pairs"]}
    expected = inventory_pairs.get(key)
    if expected is None:
        raise PairDataError("pair is absent from accepted alignment inventory")

    left, right = key
    out = synchronize_pair(
        series_by_symbol[left],
        series_by_symbol[right],
        by_symbol[left],
        by_symbol[right],
        quote_unit_authority=quote_unit_authority,
        expected_common_m5_timestamps=int(expected["common_m5_timestamps"]),
    )
    out["alignment_inventory_binding"] = {
        "ref": ALIGNMENT_INVENTORY_REF,
        "inventory_status": alignment_inventory["status"],
        "expected_common_m5_timestamps": int(expected["common_m5_timestamps"]),
        "expected_common_utc_dates": int(expected["common_utc_dates"]),
        "pair_inventory_reused_not_regenerated": True,
    }
    return out


def audit(old_zip: Path, replacement_zip: Path, registry: dict, acceptance: dict) -> dict:
    if (
        sha(old_zip.read_bytes()) != OLD_ZIP_SHA256
        or sha(replacement_zip.read_bytes()) != REPLACEMENT_ZIP_SHA256
    ):
        raise ValueError("capture transport identity does not match accepted evidence")
    reps = registry["representatives"]
    by_symbol = {r["broker_symbol"]: r for r in reps}
    if (
        len(reps) != 41
        or len(by_symbol) != 41
        or set(acceptance["series"]) != REPLACEMENTS
    ):
        raise ValueError("current structural frontier differs from accepted epoch-23 authority")
    times = {}
    observations = {}
    with ZipFile(old_zip) as old, ZipFile(replacement_zip) as replacement:
        if old.testzip() or replacement.testzip():
            raise ValueError("zip CRC failure")
        manifest = json.loads(old.read("capture_manifest.json"))
        old_series = {s["broker_symbol"]: s for s in manifest["series"]}
        for symbol, rep in sorted(by_symbol.items()):
            if symbol in REPLACEMENTS:
                bound = acceptance["series"][symbol]
                if bound["symbol_id"] != rep["symbol_id"]:
                    raise ValueError(f"replacement identity mismatch: {symbol}")
                ts, duplicates = read_series(
                    replacement,
                    bound["raw_path"],
                    bound["raw_sha256"],
                    canonicalize=True,
                )
                if (
                    len(ts) != bound["canonical_rows"]
                    or duplicates != bound["identical_duplicate_rows_removed"]
                ):
                    raise ValueError(f"replacement canonicalization mismatch: {symbol}")
                source = "EPOCH23_REPLACEMENT"
            else:
                bound = old_series[symbol]
                if bound["symbol_id"] != rep["symbol_id"]:
                    raise ValueError(f"original identity mismatch: {symbol}")
                ts, duplicates = read_series(
                    old, bound["file"], bound["sha256"], canonicalize=False
                )
                if len(ts) != bound["row_count"]:
                    raise ValueError(f"original row count mismatch: {symbol}")
                source = "ACCEPTED_13W_DEVELOPMENT"
            times[symbol] = ts
            observations[symbol] = {
                "symbol_id": rep["symbol_id"],
                "rows": len(ts),
                "source": source,
                "first_utc": min(ts),
                "last_utc": max(ts),
                "signature": rep["signature"],
                "min_margin_eur": rep["min_margin_eur"],
            }
    pairs = []
    for left, right in combinations(sorted(by_symbol), 2):
        common = times[left] & times[right]
        a, b = by_symbol[left], by_symbol[right]
        pairs.append(
            {
                "symbols": [left, right],
                "common_m5_timestamps": len(common),
                "common_utc_dates": len({s[:10] for s in common}),
                "same_asset_class": a["signature"][0] == b["signature"][0],
                "same_product_type": a["signature"][1] == b["signature"][1],
                "minimum_combined_margin_eur": round(
                    a["min_margin_eur"] + b["min_margin_eur"], 4
                ),
                "both_margins_below_eur200": a["min_margin_eur"]
                + b["min_margin_eur"]
                < 200,
            }
        )
    return {
        "schema": "mxm.greenfield.epoch24-relative-value-data-prerequisite.v1",
        "status": "COMPLETE_NON_ECONOMIC_ALIGNMENT_INVENTORY_NO_PAIR_SELECTED",
        "evidence_epoch": 23,
        "accepted_inputs": {
            "original_zip_sha256": OLD_ZIP_SHA256,
            "replacement_zip_sha256": REPLACEMENT_ZIP_SHA256,
            "registry_ref": "research_v3/CURRENT_BROKER_STRUCTURAL_SIGNATURE_REGISTRY_EPOCH22_V1.json",
            "replacement_acceptance_ref": "evidence/CURRENT_FRONTIER_REPLACEMENT_13W_M5_CAPTURE_EPOCH23_ACCEPTANCE_V1.json",
        },
        "representatives": observations,
        "pair_count": len(pairs),
        "pairs_with_any_common_bar": sum(
            p["common_m5_timestamps"] > 0 for p in pairs
        ),
        "pairs": pairs,
        "limits": [
            "Timestamp overlap is an availability check, not a cointegration test or economic signal.",
            "Representative coverage does not close the 1576-identity eligible frontier.",
            "Minimum margin excludes spread, commission, hedging, adverse moves and free-margin reserve.",
            "No pair or symbol is prospectively frozen by this inventory; independent validation and transaction-local cost authority remain prerequisites.",
        ],
        "economic_effect": {
            "v2_attempts": 0,
            "economic_outcomes": 0,
            "returns_or_pnl_computed": False,
            "protected_forward_opened": False,
        },
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--old-zip", type=Path, required=True)
    p.add_argument("--replacement-zip", type=Path, required=True)
    p.add_argument("--registry", type=Path, required=True)
    p.add_argument("--replacement-acceptance", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    result = audit(
        a.old_zip,
        a.replacement_zip,
        json.loads(a.registry.read_text()),
        json.loads(a.replacement_acceptance.read_text()),
    )
    a.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
