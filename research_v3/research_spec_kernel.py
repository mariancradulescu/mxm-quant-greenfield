"""Reusable, non-economic structural research spec runner.

The preparation step converts hash-verified accepted capture bytes into a portable
event table. It does not calculate a research result. The execution step requires
a prospectively committed spec and performs the predeclared aggregation.
"""
from __future__ import annotations

import argparse
import base64
import csv
import gzip
import hashlib
import io
import json
import statistics
import zipfile
from datetime import datetime
from pathlib import Path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_spec(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    doc = json.loads(raw)
    if doc["schema"] != "mxm.greenfield.declarative-structural-research-spec.v1":
        raise ValueError("unsupported research spec")
    if doc["safety"] != {
        "economic_outcomes_opened": 0, "v2_attempts_consumed": 0,
        "protected_forward_opened": False, "live_orders_authorized": False,
        "independent_confirmation_claim": False,
    }:
        raise ValueError("research safety boundary changed")
    if doc["statistic"]["primitive"] != "BINARY_EVENT_CHRONOLOGICAL_STABILITY_BREADTH_V1":
        raise ValueError("unregistered capability")
    return doc, digest(raw)


def parse_csv(raw: bytes, symbol: str) -> list[tuple[datetime, float, float, float]]:
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8")))
    if not {"time_utc", "open", "high", "low", "close"} <= set(reader.fieldnames or []):
        raise ValueError(f"{symbol}: malformed OHLC")
    result = []
    seen = {}
    for row in reader:
        t = datetime.fromisoformat(row["time_utc"].replace("Z", "+00:00"))
        o, h, l, c = (float(row[x]) for x in ("open", "high", "low", "close"))
        if not (l <= min(o, c) <= max(o, c) <= h):
            raise ValueError(f"{symbol}: invalid OHLC")
        if not (datetime.fromisoformat("2026-06-15T00:00:00+00:00") <= t <=
                datetime.fromisoformat("2026-09-13T23:59:59+00:00")):
            continue
        value = (t, h, l, c)
        if t in seen and seen[t] != value:
            raise ValueError(f"{symbol}: conflicting duplicate timestamp")
        seen[t] = value
    return [seen[t] for t in sorted(seen)]


def extract_events(rows: list, law: dict) -> list[list]:
    lookback = law["lookback_bars"]
    horizon = 3
    spacing = law["minimum_bars_between_selected_events_per_symbol"]
    out = []
    previous = -spacing
    for i in range(lookback, len(rows) - horizon):
        segment = rows[i-lookback:i+horizon+1]
        if any((b[0]-a[0]).total_seconds() != law["resolution_seconds"]
               for a, b in zip(segment, segment[1:])):
            continue
        prior = rows[i-lookback:i]
        direction = 1 if rows[i][3] > max(x[1] for x in prior) else (
            -1 if rows[i][3] < min(x[2] for x in prior) else 0)
        if not direction:
            continue
        baseline = statistics.median(x[1]-x[2] for x in prior)
        current_range = rows[i][1]-rows[i][2]
        if not (current_range >= law["range_at_least_prior_median_multiple"]*baseline
                if baseline > 0 else current_range > 0):
            continue
        if i-previous < spacing:
            continue
        previous = i
        difference = (rows[i+horizon][3]-rows[i][3])*direction
        out.append([rows[i][0].isoformat(), 1 if difference > 0 else
                    -1 if difference < 0 else 0])
    return out


def prepare(spec_path: Path, registry_path: Path, captures: list[Path], output: Path) -> None:
    spec, spec_hash = load_spec(spec_path)
    binding = {x["capture_sha256"]: x for x in spec["data_bindings"]}
    if {digest(p.read_bytes()) for p in captures} != set(binding):
        raise ValueError("accepted capture hash mismatch")
    registry = json.loads(registry_path.read_text())
    selected = {x["broker_symbol"] for x in registry["representatives"]}
    if len(selected) != spec["scope"]["expected_representatives"]:
        raise ValueError("representative registry breadth mismatch")
    event_table = {}
    for path in captures:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            manifest_path = next(n for n in names if n.endswith("capture_manifest.json"))
            manifest = json.loads(z.read(manifest_path))
            if manifest.get("protected_evidence_opened") is not False or manifest.get("economic_outcomes_opened") != 0:
                raise ValueError("capture safety invariant failed")
            if "series" in manifest:
                files = [(x["broker_symbol"], x["file"], x.get("sha256"))
                         for x in manifest["series"]
                         if x.get("capture_status") == "SERIES_CAPTURE_COMPLETE"]
            else:
                files = []
                for n in names:
                    if not n.endswith(".csv") or "/raw/" not in n:
                        continue
                    # Replacement CSV names are keyed by exact broker symbol ID.
                    symbol_id = int(Path(n).name.split("_", 1)[0])
                    matching = [x["broker_symbol"] for x in registry["representatives"]
                                if x["symbol_id"] == symbol_id]
                    if len(matching) == 1:
                        files.append((matching[0], n, None))
            for symbol, name, expected in files:
                if symbol not in selected:
                    continue
                raw = z.read(name)
                if expected and digest(raw) != expected:
                    raise ValueError(f"{symbol}: raw series hash mismatch")
                if symbol in event_table:
                    raise ValueError(f"{symbol}: duplicate accepted source")
                event_table[symbol] = extract_events(parse_csv(raw, symbol), spec["event"])
    if set(event_table) != selected:
        raise ValueError(f"missing current representatives: {sorted(selected-set(event_table))}")
    payload = {"schema": "mxm.greenfield.portable-binary-event-table.v1",
               "spec_sha256": spec_hash,
               "source_sha256": sorted(binding),
               "events": event_table}
    output.write_text(base64.b64encode(gzip.compress(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(),
        mtime=0)).decode() + "\n")


def execute(spec_path: Path, input_path: Path, output: Path) -> dict:
    spec, spec_hash = load_spec(spec_path)
    data = json.loads(gzip.decompress(base64.b64decode(input_path.read_text())))
    if data["spec_sha256"] != spec_hash or data["source_sha256"] != sorted(
            x["capture_sha256"] for x in spec["data_bindings"]):
        raise ValueError("input is not bound to frozen spec and accepted sources")
    rows = data["events"]
    if len(rows) != spec["scope"]["expected_representatives"]:
        raise ValueError("incomplete event table")
    law = spec["statistic"]
    results = {}
    for symbol, events in sorted(rows.items()):
        times = [datetime.fromisoformat(x[0]) for x in events]
        if times != sorted(set(times)):
            raise ValueError(f"{symbol}: event chronology invalid")
        half = (len(events)+1)//2
        partitions = (events[:half], events[half:])
        counts = []
        for part in partitions:
            continuation = sum(x[1] == 1 for x in part)
            reversal = sum(x[1] == -1 for x in part)
            flat = sum(x[1] == 0 for x in part)
            n = continuation+reversal
            counts.append({"continuation": continuation, "reversal": reversal,
                           "flat": flat, "nonflat": n,
                           "fraction": continuation/n if n else None})
        eligible = all(x["nonflat"] >= law["minimum_nonflat_events_per_half"] for x in counts)
        stable = eligible and all(x["fraction"] >= law["per_half_continuation_fraction_at_least"]
                                  for x in counts) and abs(counts[0]["fraction"]-counts[1]["fraction"]) <= law["max_absolute_half_difference"]
        results[symbol] = {"events": len(events), "halves": counts,
                           "eligible": eligible, "stable": stable}
    n = sum(x["eligible"] for x in results.values())
    stable = sum(x["stable"] for x in results.values())
    fraction = stable/n if n else None
    status = ("INSUFFICIENT_DATA" if n < law["minimum_eligible_symbols"] else
              "DESCRIPTIVE_STRUCTURAL_GATE_MET" if fraction >= law["breadth_fraction_at_least"]
              else "DESCRIPTIVE_STRUCTURAL_GATE_NOT_MET")
    result = {
        "schema": "mxm.greenfield.declarative-structural-research-result.v1",
        "status": "COMPLETE_NON_ECONOMIC",
        "spec_sha256": spec_hash,
        "input_attestation": {"sha256": digest(input_path.read_bytes()),
                              "source_capture_sha256": data["source_sha256"]},
        "symbol_results": results, "eligible_symbols": n, "stable_symbols": stable,
        "breadth_fraction": fraction, "structural_gate_status": status,
        "interpretation_boundary": "Exploratory descriptive development evidence. No independence, inferential confidence, economic edge, promotion, or family closure.",
        "economic_effect": {"economic_outcomes_opened": 0, "v2_attempts_consumed": 0,
                            "search_budget_change": 0},
    }
    output.write_text(json.dumps(result, sort_keys=True, indent=2)+"\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "execute"))
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--capture", action="append", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.spec, args.registry, args.capture, args.output)
    else:
        execute(args.spec, args.input, args.output)
