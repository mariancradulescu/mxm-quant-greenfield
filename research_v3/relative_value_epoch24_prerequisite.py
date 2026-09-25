"""Outcome-blind relative-value data alignment audit for the accepted epoch-23 frontier.

This script records every pair in the current structural representative set. It does
not fit a hedge, test cointegration, inspect returns, or select a trading pair.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from itertools import combinations
from pathlib import Path
from zipfile import ZipFile

OLD_ZIP_SHA256 = "64ea52126a31c527d2021a50923adab1b7df8f0ce5debe7f631cf4ce09b39503"
REPLACEMENT_ZIP_SHA256 = "d9be18c7aa902a83bad0417bc561b7ef8df4c3ac357ff884d98c4ee3e0cc5d75"
REPLACEMENTS = {"CXMT.CN-PERP", "ERICB.SE", "XAUUSD-F"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_series(z: ZipFile, path: str, expected_raw_hash: str, *, canonicalize: bool):
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
    if ordered != sorted(ordered):
        # Replacement capture has validated identical repeated pagination pages;
        # its canonical series is chronological after exact duplicate removal.
        if not canonicalize:
            raise ValueError(f"out-of-order timestamps: {path}")
    return set(ordered), duplicates


def audit(old_zip: Path, replacement_zip: Path, registry: dict, acceptance: dict) -> dict:
    if sha(old_zip.read_bytes()) != OLD_ZIP_SHA256 or sha(replacement_zip.read_bytes()) != REPLACEMENT_ZIP_SHA256:
        raise ValueError("capture transport identity does not match accepted evidence")
    reps = registry["representatives"]
    by_symbol = {r["broker_symbol"]: r for r in reps}
    if len(reps) != 41 or len(by_symbol) != 41 or set(acceptance["series"]) != REPLACEMENTS:
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
                ts, duplicates = read_series(replacement, bound["raw_path"], bound["raw_sha256"], canonicalize=True)
                if len(ts) != bound["canonical_rows"] or duplicates != bound["identical_duplicate_rows_removed"]:
                    raise ValueError(f"replacement canonicalization mismatch: {symbol}")
                source = "EPOCH23_REPLACEMENT"
            else:
                bound = old_series[symbol]
                if bound["symbol_id"] != rep["symbol_id"]:
                    raise ValueError(f"original identity mismatch: {symbol}")
                ts, duplicates = read_series(old, bound["file"], bound["sha256"], canonicalize=False)
                if len(ts) != bound["row_count"]:
                    raise ValueError(f"original row count mismatch: {symbol}")
                source = "ACCEPTED_13W_DEVELOPMENT"
            times[symbol] = ts
            observations[symbol] = {"symbol_id": rep["symbol_id"], "rows": len(ts),
                                    "source": source, "first_utc": min(ts), "last_utc": max(ts),
                                    "signature": rep["signature"], "min_margin_eur": rep["min_margin_eur"]}
    pairs = []
    for left, right in combinations(sorted(by_symbol), 2):
        common = times[left] & times[right]
        a, b = by_symbol[left], by_symbol[right]
        pairs.append({"symbols": [left, right], "common_m5_timestamps": len(common),
                      "common_utc_dates": len({s[:10] for s in common}),
                      "same_asset_class": a["signature"][0] == b["signature"][0],
                      "same_product_type": a["signature"][1] == b["signature"][1],
                      "minimum_combined_margin_eur": round(a["min_margin_eur"] + b["min_margin_eur"], 4),
                      "both_margins_below_eur200": a["min_margin_eur"] + b["min_margin_eur"] < 200})
    return {"schema": "mxm.greenfield.epoch24-relative-value-data-prerequisite.v1",
            "status": "COMPLETE_NON_ECONOMIC_ALIGNMENT_INVENTORY_NO_PAIR_SELECTED",
            "evidence_epoch": 23,
            "accepted_inputs": {"original_zip_sha256": OLD_ZIP_SHA256,
                                "replacement_zip_sha256": REPLACEMENT_ZIP_SHA256,
                                "registry_ref": "research_v3/CURRENT_BROKER_STRUCTURAL_SIGNATURE_REGISTRY_EPOCH22_V1.json",
                                "replacement_acceptance_ref": "evidence/CURRENT_FRONTIER_REPLACEMENT_13W_M5_CAPTURE_EPOCH23_ACCEPTANCE_V1.json"},
            "representatives": observations, "pair_count": len(pairs),
            "pairs_with_any_common_bar": sum(p["common_m5_timestamps"] > 0 for p in pairs),
            "pairs": pairs,
            "limits": ["Timestamp overlap is an availability check, not a cointegration test or economic signal.",
                       "Representative coverage does not close the 1576-identity eligible frontier.",
                       "Minimum margin excludes spread, commission, hedging, adverse moves and free-margin reserve.",
                       "No pair or symbol is prospectively frozen by this inventory; independent validation and transaction-local cost authority remain prerequisites."],
            "economic_effect": {"v2_attempts": 0, "economic_outcomes": 0,
                                "returns_or_pnl_computed": False, "protected_forward_opened": False}}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--old-zip", type=Path, required=True)
    p.add_argument("--replacement-zip", type=Path, required=True)
    p.add_argument("--registry", type=Path, required=True)
    p.add_argument("--replacement-acceptance", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    result = audit(a.old_zip, a.replacement_zip,
                   json.loads(a.registry.read_text()),
                   json.loads(a.replacement_acceptance.read_text()))
    a.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
