"""Frozen descriptive M5 serial-dependence screen; no economic outcomes."""
import csv
import hashlib
import io
import json
import math
import sys
import zipfile
from datetime import datetime
from pathlib import Path

SOURCE_SHA = "64ea52126a31c527d2021a50923adab1b7df8f0ce5debe7f631cf4ce09b39503"
HORIZONS = (1, 3, 6)


def correlation(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    xx = sum((x - mx) ** 2 for x in xs)
    yy = sum((y - my) ** 2 for y in ys)
    if xx == 0 or yy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(xx * yy)


def run(path):
    path = Path(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != SOURCE_SHA:
        raise ValueError("Accepted capture SHA mismatch")
    report = {}
    pooled = {h: ([], []) for h in HORIZONS}
    with zipfile.ZipFile(path) as archive:
        names = sorted(n for n in archive.namelist() if n.startswith("raw/") and n.endswith("_M5.csv"))
        if len(names) != 40:
            raise ValueError("Expected exactly 40 accepted M5 series")
        for name in names:
            rows = list(csv.DictReader(io.TextIOWrapper(archive.open(name), encoding="utf-8")))
            times = [datetime.fromisoformat(r["time_utc"].replace("Z", "+00:00")) for r in rows]
            closes = [float(r["close"]) for r in rows]
            if any(p <= 0 or not math.isfinite(p) for p in closes):
                raise ValueError("Invalid close in " + name)
            values = {}
            for h in HORIZONS:
                xs, ys = [], []
                for t in range(1, len(rows) - h):
                    if any((times[k] - times[k-1]).total_seconds() != 300 for k in range(t, t+h+1)):
                        continue
                    x = math.log(closes[t] / closes[t-1])
                    y = math.log(closes[t+h] / closes[t])
                    xs.append(x)
                    ys.append(y)
                pooled[h][0].extend(xs)
                pooled[h][1].extend(ys)
                values[str(h)] = {"observations": len(xs), "correlation": correlation(xs, ys)}
            report[name] = values
    return {"schema": "mxm.greenfield.epoch20-serial-dependence-screen.v1",
            "status": "COMPLETE_NON_ECONOMIC_DESCRIPTIVE_SCREEN",
            "source_zip_sha256": SOURCE_SHA,
            "frozen_horizons_m5_bars": list(HORIZONS),
            "series": report,
            "pooled": {str(h): {"observations":len(pooled[h][0]),
                                "correlation":correlation(*pooled[h])} for h in HORIZONS},
            "economic_effect": {"outcomes_opened":0,"attempts_consumed":0,"budget_change":0},
            "interpretation_boundary": "Descriptive development statistics, not PnL, significance, candidate selection or family closure."}


if __name__ == "__main__":
    print(json.dumps(run(sys.argv[1]), indent=2, sort_keys=True))
