"""Outcome-blind inventory of already accepted broker-native M5 captures.

No strategy entry, exit, P&L, forward label, or candidate selection is computed.
Source ZIP bytes remain external to Git and must match the acceptance hashes.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import statistics
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

SOURCES = (
    ("development_13w", "64ea52126a31c527d2021a50923adab1b7df8f0ce5debe7f631cf4ce09b39503"),
    ("replacement_13w", "d9be18c7aa902a83bad0417bc561b7ef8df4c3ac357ff884d98c4ee3e0cc5d75"),
    ("crossalign_four_m5", "36de60e2991bec99596b5b11da43efe3d62dafa8747c043a25c394fd3f9a4d49"),
    ("crossmarket_four_disjoint_m5", "db4ec267b79df73a2d10fbefa66973f2c637a05b0abd878691709cb34518fed9"),
)
PEER_REF = "evidence/CROSS_SECTIONAL_PEER_COHORT_INDEX_V1.json"
PREFLIGHT_REF = "evidence/EPOCH39_MEAN_REVERSION_SCOPE_POWER_PREFLIGHT_V1.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_series(archive: zipfile.ZipFile, name: str) -> list[tuple[datetime, float]]:
    reader = csv.DictReader(io.TextIOWrapper(archive.open(name), encoding="utf-8"))
    rows = []
    for row in reader:
        close = float(row["close"])
        if close <= 0 or not math.isfinite(close):
            raise ValueError(f"invalid close in {name}")
        stamp = row.get("time_utc") or row.get("timestamp")
        if not stamp:
            raise ValueError(f"timestamp column missing in {name}")
        rows.append((datetime.fromisoformat(stamp.replace("Z", "+00:00")), close))
    canonical = {}
    for timestamp, close in rows:
        if timestamp in canonical and canonical[timestamp] != close:
            raise ValueError(f"conflicting duplicate timestamp in {name}")
        canonical[timestamp] = close
    return sorted(canonical.items())


def build(root: Path, source_paths: dict[str, Path]) -> dict:
    peers = json.loads((root / PEER_REF).read_text())
    preflight = json.loads((root / PREFLIGHT_REF).read_text())
    identities = peers["identities"]
    if len(identities) != 1576 or preflight["scope"]["sampling_frame_size"] != 1576:
        raise ValueError("full eligible frame mismatch")
    frame = {int(row["symbol_id"]): row for row in identities}
    if len(frame) != 1576 or peers["source_bindings"]["eligible_identity_set_sha256"] != preflight["scope"]["identity_set_sha256"]:
        raise ValueError("eligible identity binding mismatch")
    observed: dict[int, list[dict]] = defaultdict(list)
    source_attestation = []
    for label, expected_hash in SOURCES:
        path = source_paths.get(label)
        if path is None:
            source_attestation.append({"source": label, "status": "ACCEPTED_BYTES_NOT_MATERIALIZED_IN_THIS_RUN", "expected_zip_sha256": expected_hash})
            continue
        if _sha(path) != expected_hash:
            raise ValueError(f"accepted ZIP hash mismatch: {label}")
        with zipfile.ZipFile(path) as archive:
            manifest = json.loads(archive.read("capture_manifest.json"))
            files = [n for n in archive.namelist() if n.startswith("raw/") and n.endswith("_M5.csv")]
            # Replacement transports can contain a second directory copy; consume
            # canonical root raw/ paths exactly once.
            for name in sorted(set(files)):
                sid = int(name.split("/", 1)[1].split("_", 1)[0])
                if sid not in frame:
                    continue
                rows = _read_series(archive, name)
                if rows:
                    observed[sid].append({"source": label, "file": name, "rows": rows})
            source_attestation.append({"source": label, "status": "HASH_VERIFIED_AND_READ", "zip_sha256": expected_hash,
                                       "manifest_schema": manifest.get("schema"), "canonical_raw_file_count": len(files)})
    results = []
    for sid, identity in sorted(frame.items()):
        captures = observed.get(sid, [])
        rows_by_time = {}
        for capture in captures:
            for timestamp, close in capture["rows"]:
                old = rows_by_time.setdefault(timestamp, close)
                if old != close:
                    raise ValueError(f"conflicting accepted close for {sid} at {timestamp}")
        ordered = sorted(rows_by_time.items())
        dates = {t.date() for t, _ in ordered}
        # Adjacent *observed* M5 bars only. Gaps do not become inferred returns.
        differences = []
        for (t0, c0), (t1, c1) in zip(ordered, ordered[1:]):
            if (t1 - t0).total_seconds() == 300:
                differences.append(math.log(c1 / c0))
        signs = [1 if x > 0 else -1 if x < 0 else 0 for x in differences]
        sign_pairs = [(a, b) for a, b in zip(signs, signs[1:]) if a and b]
        reversals = sum(a != b for a, b in sign_pairs)
        span_slots = sum(1 + int((last - first).total_seconds() // 300)
                         for first, last in _date_spans(ordered))
        results.append({
            "symbol_id": sid, "broker_symbol": identity["broker_symbol"],
            "source_labels": sorted({x["source"] for x in captures}),
            "observed_m5_bars": len(ordered), "active_utc_dates": len(dates),
            "observed_date_span_m5_slot_coverage_proxy": round(len(ordered) / span_slots, 6) if span_slots else None,
            "coverage_proxy_caveat": "Within observed first/last bar per UTC date; exchange schedule, lunch breaks and genuine missing bars are not distinguished.",
            "adjacent_m5_price_changes": len(differences),
            "sign_reversal_proxy_count": reversals,
            "sign_reversal_proxy_rate": round(reversals / len(sign_pairs), 6) if sign_pairs else None,
            "median_abs_adjacent_log_price_change": round(statistics.median(map(abs, differences)), 10) if differences else None,
            "usable_for_descriptive_stage1": len(ordered) >= 3,
            "missingness_class": "NO_HASH_VERIFIED_M5_BYTES_IN_THIS_RUN" if not ordered else "OBSERVED_ONLY_SCHEDULE_ADJUSTED_COMPLETENESS_UNKNOWN",
        })
    return {
        "schema": "mxm.greenfield.epoch40-mean-reversion-stage1-outcome-blind-triage.v1",
        "status": "COMPLETE_BOUNDED_OUTCOME_BLIND_ACCEPTED_CAPTURE_TRIAGE",
        "family": "MEAN_REVERSION", "evidence_epoch": 40,
        "source_authority": {"peer_index_ref": PEER_REF, "preflight_ref": PREFLIGHT_REF,
                             "eligible_identity_set_sha256": preflight["scope"]["identity_set_sha256"],
                             "captures": source_attestation},
        "coverage": {"eligible_identities": 1576, "identities_with_verified_m5_bars": sum(r["observed_m5_bars"] > 0 for r in results),
                     "identities_without_verified_m5_bars_in_this_run": sum(r["observed_m5_bars"] == 0 for r in results),
                     "other_accepted_capture_scopes": "NOT_MATERIALIZED_OR_HASH_VERIFIED_IN_THIS_RUN; no absence claim"},
        "identities": results,
        "interpretation_boundary": {"economic_promotion_authorized": False, "candidate_identity_created": False,
                                    "independent_confirmation_claimed": False, "structural_41_inferential_panel": False,
                                    "strategy_outcomes_read": False, "mechanism_family_closed": False},
        "accounting_effect": {"v2_attempts_consumed": 0, "economic_outcomes_opened": 0, "search_budget_change": 0},
        "safety": {"protected_forward_opened": False, "live_orders_authorized": False},
        "next_gate": "Inspect other accepted capture scopes and schedule-adjusted completeness before prospective cohort or new broker data scope; do not select economic candidates from this proxy.",
    }


def _date_spans(rows):
    grouped = defaultdict(list)
    for timestamp, _ in rows:
        grouped[timestamp.date()].append(timestamp)
    return ((min(ts), max(ts)) for ts in grouped.values())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--development", type=Path, required=True)
    p.add_argument("--replacement", type=Path, required=True)
    p.add_argument("--crossalign", type=Path, required=True)
    p.add_argument("--crossmarket", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = build(args.root, {"development_13w": args.development, "replacement_13w": args.replacement,
                               "crossalign_four_m5": args.crossalign, "crossmarket_four_disjoint_m5": args.crossmarket})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result["coverage"], sort_keys=True))


if __name__ == "__main__":
    main()
