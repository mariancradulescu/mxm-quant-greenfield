from __future__ import annotations

import json
import math
import time
from datetime import datetime, timedelta, timezone

try:
    from research_core_v4 import response_evaluator_v3 as ev
except ModuleNotFoundError:
    import response_evaluator_v3 as ev


def synthetic_fixture(n: int = 6000):
    contexts = ev.CONTEXTS
    symbols = {c: [f"SYN_{i}_{c}" for i in range(6)] for c in contexts}
    events = []
    norm = {}
    raw = {}
    base = datetime(2025, 9, 16, tzinfo=timezone.utc)
    for i in range(n):
        context = contexts[i % 3]
        symbol = symbols[context][(i // 3) % 6]
        direction = 1 if (i // 18) % 2 == 0 else -1
        state = "LOW" if (i // 36) % 2 == 0 else "HIGH"
        arm = "FULL" if (i // 72) % 2 == 0 else "BASELINE"
        trigger = base + timedelta(minutes=15 * i)
        if context == "US_EQUITY_EXTENDED_HOURS":
            session = "REGULAR"
            dst = "DST" if i % 2 == 0 else "STANDARD"
        else:
            session = ("ASIA_UTC", "EUROPE_UTC", "US_UTC", "LATE_UTC")[(trigger.hour // 6) % 4]
            dst = None
        event = ev.SignalEvent(
            context, symbol, i % 18 + 1, trigger, direction, state, arm,
            100.0, 0.01, ev.iso_week_key(trigger), (True, True, True, True),
            trigger.hour, trigger.strftime("%A"), session, dst,
        )
        events.append(event)
        for horizon in ev.HORIZONS:
            value = (
                0.01 * math.sin((i + 1) * 0.0017 + horizon * 0.13)
                + (0.0002 if arm == "FULL" else -0.0001)
            )
            norm[(symbol, trigger, horizon)] = value
            raw[(symbol, trigger, horizon)] = value * 100.0
    return events, norm, raw


def run_profile(n: int = 6000) -> dict:
    events, norm, raw = synthetic_fixture(n)
    t0 = time.perf_counter()
    units = ev.construct_paired_units(events, norm)
    t1 = time.perf_counter()

    original = ev.construct_paired_units
    calls = {"count": 0}

    def counted(*args, **kwargs):
        calls["count"] += 1
        return original(*args, **kwargs)

    ev.construct_paired_units = counted
    try:
        diagnostics = ev.build_nonselection_diagnostics(events, norm, raw)
    finally:
        ev.construct_paired_units = original
    t2 = time.perf_counter()

    diagnostic_rows = sum(len(x["rows"]) for x in diagnostics.values())
    expected_pair_rebuild_calls = 2 * diagnostic_rows
    if calls["count"] != expected_pair_rebuild_calls:
        raise AssertionError((calls["count"], expected_pair_rebuild_calls))
    for item in diagnostics.values():
        if item["classification"] != "NONSELECTION_ONLY" or item["may_change_lead_verdict"] is not False:
            raise AssertionError("diagnostic selection boundary changed")

    return {
        "schema": "mxm.research-core-v4.synthetic-runtime-profile.v1",
        "status": "PASS",
        "synthetic_only": True,
        "real_market_response_values_used": False,
        "event_count": len(events),
        "paired_units_once": len(units),
        "paired_units_once_seconds": t1 - t0,
        "nonselection_diagnostics_seconds": t2 - t1,
        "diagnostic_rows": diagnostic_rows,
        "construct_paired_units_calls_inside_diagnostics": calls["count"],
        "expected_construct_paired_units_calls": expected_pair_rebuild_calls,
        "hotspot_verified": calls["count"] == expected_pair_rebuild_calls,
        "seed_or_permutation_law_touched": False,
    }


if __name__ == "__main__":
    print(json.dumps(run_profile(), sort_keys=True))
