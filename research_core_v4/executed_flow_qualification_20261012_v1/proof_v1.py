"""Schema/projection proof only. NO market returns, requests, or orders.

Run from the scratch root with --source-root evidence_inputs, or from a
checkout with --source-root . . All input bytes are SHA256-bound in output.
Synthetic latent-flow witnesses are not Pepperstone observations.
"""
import argparse
import hashlib
import itertools
import json
import re
from pathlib import Path

BASE_HEAD = "2b5a51096dbcde47f3f42464c167cb4b5a3528d5"
PATHS = [
    "research_core_v4/nonmarket_contract_v3/OpenApiMessages.proto",
    "research_core_v4/nonmarket_contract_v3/OpenApiModelMessages.proto",
    "research_core_v4/cost_frequency_discovery_v1/collector_v1.py",
    "research_core_v4/wide_greenfield_v1/collect_v2.py",
    "research_core_v4/native_update_asymmetry_v1/DESIGN_V1.json",
    "research_core_v4/integrated_alpha_campaign_v1/DESIGN_FREEZE_V1.json",
]

def fields(source, message):
    match = re.search(r"message\s+" + message + r"\s*\{(.*?)\n\}", source, re.S)
    if not match:
        raise AssertionError("MISSING_MESSAGE:" + message)
    return set(re.findall(r"(?:required|optional|repeated)\s+\w+\s+(\w+)\s*=", match[1]))

def projection(world):
    # Historical quote schema has no mapping from market-wide trades to quotes.
    # Dropping unobserved flow is the observation map; no market impact law assumed.
    return world["bid"], world["ask"], world["bar_tick_count"]

def pressure(world):
    total = sum(size for _, size in world["executions"])
    return sum(side * size for side, size in world["executions"]) / total

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args()
    raw = {p: (args.source_root / p).read_bytes() for p in PATHS}
    text = {p: value.decode("utf-8") for p, value in raw.items()}
    msgs, model, m5, quote, asymmetry, campaign = [text[p] for p in PATHS]
    checks = []

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append({"test": name, "status": "PASS"})

    check("historical_tick_exact_fields", fields(model, "ProtoOATickData") == {"timestamp", "tick"})
    check("tick_request_quote_side_not_aggressor", fields(msgs, "ProtoOAGetTickDataReq") == {
        "payloadType", "ctidTraderAccountId", "symbolId", "type", "fromTimestamp", "toTimestamp"})
    check("trendbar_volume_is_tick_count", "Bar volume in ticks." in model
          and "('open','high','low','close','tick_volume')" in m5)
    check("collector_quote_price_time_only", "{'timestamp':int(x.timestamp),'tick':int(x.tick)}" in quote)
    check("deal_side_not_in_historical_quote_response", "tradeSide" in fields(model, "ProtoOADeal")
          and "tradeSide" not in fields(model, "ProtoOATickData")
          and "deal" not in fields(msgs, "ProtoOAGetTickDataRes"))
    check("displayed_depth_not_executed_flow", "size" in fields(model, "ProtoOADepthQuote")
          and "tradeSide" not in fields(model, "ProtoOADepthQuote")
          and "filledVolume" not in fields(model, "ProtoOADepthQuote"))
    old = json.loads(asymmetry)
    integrated = json.loads(campaign)
    check("prior_quote_count_exact_preserved", "count_bid60s - count_ask60s" in old["causal_estimand"])
    check("prior_activity_low_impact_exact_preserved", any(
        f["name"] == "MATCHED_ACTIVITY_LOW_IMPACT" and "tick count" in f["direction"]
        for f in integrated["families"]))

    collisions = []
    for quote_steps in itertools.product((0, 1), repeat=4):
        bids = tuple(100 + step for step in quote_steps)
        asks = tuple(b + 2 for b in bids)
        worlds = [{"bid": bids, "ask": asks, "bar_tick_count": 4,
                   "executions": ((direction, 10), (direction, 20))}
                  for direction in (-1, 1)]
        assert projection(worlds[0]) == projection(worlds[1])
        assert pressure(worlds[0]) == -1 and pressure(worlds[1]) == 1
        collisions.append({"same_observables": True, "opposite_latent_flow": True})
    check("16_observation_collisions_opposite_flow", len(collisions) == 16)

    output = {
        "schema": "mxm.signed.execution.flow.identifiability.v1",
        "base_head": BASE_HEAD,
        "classification": "SOURCE_SCHEMA_AND_SYNTHETIC_LOGICAL_PROOF_NOT_MARKET_PILOT",
        "hypothesis": "SIGNED_EXECUTED_FLOW_PERSISTENCE_DURING_PRICE_STALL_V1",
        "decision": "NOT_QUALIFIED_INPUT_NOT_IDENTIFIABLE_FROM_REVIEWED_HISTORY",
        "source_sha256": {p: hashlib.sha256(value).hexdigest() for p, value in raw.items()},
        "checks": checks,
        "synthetic_quote_traces": 16,
        "synthetic_latent_worlds": 32,
        "ambiguity_pairs": 16,
        "market_rows_read": 0,
        "market_pilots": 0,
        "broker_requests": 0,
        "orders": 0,
        "NET_eur": None,
        "HARD21_demonstrated": False,
        "limited_conclusion": "No deterministic recovery of market-wide signed executed volume from this schema without additional assumptions or observations. Statistical quote proxies may still be useful; their predictive value is NOT disproved here.",
        "not_claimed": ["PEPPERSTONE_GLOBAL_EXHAUSTION", "ECONOMIC_NULL", "NEW_ALPHA", "CAUSAL_MARKET_IDENTIFICATION", "ALL_PRIVATE_ARCHIVES_INSPECTED"],
    }
    print(json.dumps(output, sort_keys=True, indent=2))

if __name__ == "__main__":
    main()
