"""Non-directional, nonoutcome market-movement envelope from EXACT preserved Pepperstone M5.
Reads only the existing 100 encrypted release shards in native GitHub custody.
No cTrader session, no external market data, no signals, PnL, order or parameter fitting.
Full source exposure of 1576 identities is recorded, not scientific confirmation.
"""
import argparse
import collections
import datetime as dt
import hashlib
import json
import math
import os
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
REPO = "mariancradulescu/mxm-quant-greenfield"
MANIFEST = ROOT / "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_FINAL_DURABLE_MANIFEST_V1.json"
RELEASE_IDENTITY = "mxm-shallow-m5-v2-v4-ac8322bd8e44786c3f6e1c5707079bc7eaa370c8db44f9053b9b84dfac3a2ce0"
PROTECTED_START = "2026-09-17T00:00:00Z"
STARTS = ("2026-08-20", "2026-08-27", "2026-09-03", "2026-09-10")
ENDS = ("2026-08-26", "2026-09-02", "2026-09-09", "2026-09-16")
HORIZONS = (1, 3, 12)
PRICE_HURDLES_BPS = (5, 10, 20)

def require(ok, name):
    if not ok:
        raise ValueError("MXM_M5_ENVELOPE_FAIL_" + name)

def digest(blob):
    return hashlib.sha256(blob).hexdigest()

def gh_json(path):
    result = subprocess.run(["gh", "api", path], capture_output=True, check=True, text=True)
    return json.loads(result.stdout)

def analysis_bucket():
    return {"bars": 0, "identities_with_bars": 0, "contiguous_windows": {
        str(h): {"count": 0, "abs_move_ge_5bps": 0,
                 "abs_move_ge_10bps": 0, "abs_move_ge_20bps": 0}
        for h in HORIZONS
    }}

def inspect_rows(rows, segment, bucket):
    if not rows:
        return (None, None)
    bucket["identities_with_bars"] += 1
    bucket["bars"] += len(rows)
    times, closes = [], []
    lower, upper = STARTS[segment - 1], ENDS[segment - 1]
    for row in rows:
        require(set(row) == {"time_utc", "open", "high", "low", "close", "tick_volume"}, "ROW_SCHEMA")
        stamp = row["time_utc"]
        require(stamp.endswith("Z") and lower <= stamp[:10] <= upper
                and stamp < PROTECTED_START, "TIME_FENCE")
        timestamp = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        ms = int(timestamp.timestamp() * 1000)
        require(ms % 300000 == 0 and (not times or ms > times[-1]), "M5_ORDER")
        o, hi, lo, cl = (float(row[x]) for x in ("open", "high", "low", "close"))
        require(all(math.isfinite(x) and x > 0 for x in (o, hi, lo, cl))
                and lo <= o <= hi and lo <= cl <= hi
                and int(row["tick_volume"]) >= 0, "PRICE_VOLUME")
        times.append(ms)
        closes.append(cl)
    for h in HORIZONS:
        cell = bucket["contiguous_windows"][str(h)]
        for i in range(len(rows) - h):
            # A full sequence of exactly h observed M5 bars, no interpolation over gaps.
            if times[i + h] - times[i] != 300000 * h:
                continue
            cell["count"] += 1
            # Absolute future price movement is a NON-DIRECTIONAL upper envelope,
            # not a trading decision, executable spread, net return, or profit.
            movement = abs(closes[i + h] - closes[i]) / closes[i] * 10000
            for bps in PRICE_HURDLES_BPS:
                if movement >= bps:
                    cell["abs_move_ge_%dbps" % bps] += 1
    return (rows[0]["time_utc"], rows[-1]["time_utc"])

def selftest():
    start = dt.datetime(2026, 8, 20, tzinfo=dt.timezone.utc)
    rows = []
    for i, p in enumerate((1.000, 1.002, 1.001, 1.004, 1.001, 1.006,
                           1.003, 1.002, 1.008, 1.004, 1.003, 1.005, 1.007)):
        stamp = start + dt.timedelta(minutes=5*i)
        rows.append({"time_utc": stamp.isoformat().replace("+00:00", "Z"),
            "open": str(p), "high": str(p + .001), "low": str(p - .001),
            "close": str(p), "tick_volume": "4"})
    b = analysis_bucket()
    first, last = inspect_rows(rows, 1, b)
    require(first.startswith("2026-08-20") and last.startswith("2026-08-20"), "SELFTEST_TIME")
    require(b["bars"] == 13 and b["contiguous_windows"]["1"]["count"] == 12
            and b["contiguous_windows"]["3"]["count"] == 10
            and b["contiguous_windows"]["12"]["count"] == 1, "SELFTEST_COUNTS")
    rows[5]["time_utc"] = "2026-09-17T00:00:00Z"
    try:
        inspect_rows(rows, 1, analysis_bucket())
    except ValueError as exc:
        require("TIME_FENCE" in str(exc), "SELFTEST_PROTECTION")
    else:
        require(False, "SELFTEST_PROTECTION")
    print("MXM_M5_AUTHENTIC_ENVELOPE_SELFTEST_PASS")

def protected_run(output_dir):
    # The historic, frozen manifest and release are the ONLY permitted market source.
    manifest = json.loads(MANIFEST.read_text())
    entries = manifest["entries"]
    require(manifest["status"] == "COMPLETE" and
            manifest["DURABLE_RELEASE_IDENTITY"] == RELEASE_IDENTITY and
            manifest["PROTECTED_FORWARD_ROW_COUNT"] == 0 and
            manifest["segment_count"] == 4 and manifest["encrypted_shard_count"] == 100 and
            len(entries) == 100, "MANIFEST")
    require(sum(x["ROW_COUNT"] for x in entries) == 3355389, "MANIFEST_TOTAL")
    expected = {e["ENCRYPTED_ASSET_NAME"]: e for e in entries}
    require(len(expected) == 100, "MANIFEST_UNIQUE")
    require({(x["SEGMENT_INDEX"], x["SHARD_INDEX"]) for x in entries} ==
            {(s, sh) for s in range(1, 5) for sh in range(25)}, "SHARD_GEOMETRY")
    release = gh_json("repos/" + REPO + "/releases/tags/" + RELEASE_IDENTITY)
    require(release["tag_name"] == RELEASE_IDENTITY and
            release["target_commitish"] == manifest["ARM_COMMIT"] and
            release["draft"] is False and len(release["assets"]) == 100, "RELEASE")
    actual = {x["name"]: x for x in release["assets"]}
    require(set(actual) == set(expected), "RELEASE_ASSET_SET")
    for name, e in expected.items():
        metadata = actual[name]
        require(metadata["state"] == "uploaded" and metadata["digest"] ==
                "sha256:" + e["ENCRYPTED_ASSET_SHA256"], "RELEASE_ASSET_DIGEST")
    from research_core_v4.shallow_m5_support_v2_production import decrypt_synthetic_package
    from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret
    result = {"schema": "mxm.pepperstone.m5.authentic-absolute-movement-envelope.v1",
        "data_provenance": "existing_shallow_m5_v4_release_only",
        "release_identity": RELEASE_IDENTITY,
        "manifest_sha256": digest(MANIFEST.read_bytes()),
        "event_window": ["2026-08-20T00:00:00Z", "2026-09-16T23:55:00Z"],
        "exposure": "1576 symbol identities x four pre-protected segments; non-directional statistics only",
        "statistic": "absolute close-to-close move (bps), zero knowledge of direction/executable fills",
        "hurdles_are_hypothetical_not_broker_costs": True,
        "rows_verified": 0, "shards_verified": 0,
        "by_segment": {str(s): analysis_bucket() for s in range(1, 5)},
        "directional_strategy_trials": 0, "economic_orders": 0, "historical_fills": 0,
        "euros_profit_estimated": False, "hard21_evaluated": False,
        "confirmation_or_protected_forward_opened": False,
        "new_broker_requests": 0, "new_market_providers": 0,
        "scientific_selection_or_advantage_claim": False}
    with tempfile.TemporaryDirectory(prefix="mxm-m5-envelope-") as temp:
        dirpath = pathlib.Path(temp)
        key, fp = _private_key_from_secret(dirpath)
        require(fp == "464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11", "KEY_IDENTITY")
        release_dir = dirpath / "market"
        release_dir.mkdir(mode=0o700)
        subprocess.run(["gh", "release", "download", RELEASE_IDENTITY,
                        "--repo", REPO, "--dir", str(release_dir)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        require({x.name for x in release_dir.iterdir()} == set(expected), "DOWNLOAD_SET")
        for e in sorted(entries, key=lambda x: (x["SEGMENT_INDEX"], x["SHARD_INDEX"])):
            name = e["ENCRYPTED_ASSET_NAME"]
            ciphertext = (release_dir / name).read_bytes()
            require(digest(ciphertext) == e["ENCRYPTED_ASSET_SHA256"], "CIPHERTEXT_SHA")
            raw = decrypt_synthetic_package(ciphertext, private_key=key)
            require(digest(raw) == e["PLAINTEXT_CANONICAL_SHA256"], "PLAINTEXT_SHA")
            shard = json.loads(raw)
            require(shard["schema"] == "mxm.v4.shallow-m5-v2.raw-shard.v1" and
                    shard["segment_index"] == e["SEGMENT_INDEX"] and
                    shard["shard_index"] == e["SHARD_INDEX"] and
                    shard["identity_range"] == e["IDENTITY_RANGE"], "SHARD_IDENTITY")
            observed = 0
            mins, maxs = [], []
            expected_ordinals = list(range(e["IDENTITY_RANGE"][0], e["IDENTITY_RANGE"][1] + 1))
            require([z["ordinal"] for z in shard["items"]] == expected_ordinals, "ORDINALS")
            for item in shard["items"]:
                require(isinstance(item["rows"], list), "ITEM_ROWS")
                observed += len(item["rows"])
                first, last = inspect_rows(item["rows"], e["SEGMENT_INDEX"],
                    result["by_segment"][str(e["SEGMENT_INDEX"])])
                if first is not None:
                    mins.append(first)
                    maxs.append(last)
            require(observed == e["ROW_COUNT"], "ROW_COUNT")
            require((min(mins) if mins else None) == e["FIRST_TIMESTAMP"] and
                    (max(maxs) if maxs else None) == e["LAST_TIMESTAMP"], "SHARD_TIME")
            result["rows_verified"] += observed
            result["shards_verified"] += 1
    require(result["rows_verified"] == 3355389 and result["shards_verified"] == 100,
            "COMPLETE_RECONCILIATION")
    out = pathlib.Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / "receipt.json"
    dest.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    print("MXM_M5_AUTHENTIC_ENVELOPE_RECEIPT " + json.dumps(result, sort_keys=True))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--protected-output")
    args = p.parse_args()
    require(bool(args.selftest) != bool(args.protected_output), "MODE")
    if args.selftest:
        selftest()
    else:
        require(os.environ.get("GITHUB_REPOSITORY") == REPO and
                os.environ.get("GITHUB_REF") == "refs/heads/mxm-remediation-p0-p4-20261015-v1"
                and os.environ.get("GITHUB_RUN_ATTEMPT") == "1", "CUSTODY_TRIGGER")
        protected_run(args.protected_output)

if __name__ == "__main__":
    main()
