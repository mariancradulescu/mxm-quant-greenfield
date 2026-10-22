#!/usr/bin/env python3
"""Read-only receipt integrity check for *previously exposed* stop-risk sensitivity.

This is an anti-misreporting control, NOT authentication of actual broker fills,
independent scientific confirmation, strategy selection, or HARD21 proof.
"""
import json
from decimal import Decimal, InvalidOperation
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RECEIPT = ROOT / "docs/economic-development/20261022/STOP_RISK_CAPACITY_BIDASK_READBACK_V1.json"
PREREG = Path(__file__).resolve().parent / "STOP_RISK_CAPACITY_DIAGNOSTIC_V1.json"

# Exact *already disclosed* observations, frozen to detect partial/altered readbacks.
# Keys: fractional account-risk budget, hypothetical EUR round-trip reserve.
# Values: modeled entries, rejections, modeled end-of-window EUR equity.
EXPOSED = {
    (Decimal("0.005"), Decimal("0.2")): (0, 23, Decimal("200")),
    (Decimal("0.005"), Decimal("1")): (0, 23, Decimal("200")),
    (Decimal("0.01"), Decimal("0.2")): (7, 0, Decimal("197.381818")),
    (Decimal("0.01"), Decimal("1")): (0, 23, Decimal("200")),
    (Decimal("0.02"), Decimal("0.2")): (7, 0, Decimal("197.381818")),
    (Decimal("0.02"), Decimal("1")): (7, 0, Decimal("197.381818")),
}

def require(condition, reason):
    if not condition:
        raise ValueError(reason)

def decimal(value):
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("non-numeric value") from exc
    require(d.is_finite(), "non-finite monetary/risk value")
    return d

def validate(readback, prereg):
    fixed = prereg["fixed_matrix"]
    planned = set(product(
        (decimal(x) for x in fixed["max_estimated_stop_risk_fractions"]),
        (decimal(x) for x in fixed["estimated_roundtrip_friction_reserve_eur"])
    ))
    require(planned == set(EXPOSED) and fixed["dependent_cells"] == 6,
            "preregistered matrix is not the exact original six-cell matrix")
    require(readback["schema"] == "mxm.csharp.account-risk-capacity-original-pepperstone-readback.v1",
            "unknown receipt schema")
    require(readback["scientific_classification"] ==
            "DEVELOPMENT_EXPOSED_ENGINEERING_CAPACITY_ONLY_NO_INDEPENDENT_ECONOMIC_SELECTION",
            "scientific exposure was incorrectly promoted")
    require(readback["experiment_source_run"] == prereg["exact_previous_source_run"] == 39660692230
            and readback["execution_workflow_run"] == 39810418021
            and readback["source_head_sha"] == "1485d7e23aed709455b626a9ef72dace63c6010d",
            "run/source provenance mismatch")
    require(readback["quote_cipher_sha256"] ==
            "f1d828d94b304e2af1f310701f92dcb31db935a8db7fc3f8772087adf5499346",
            "locked quote source changed")
    require(readback["encrypted_private_result_sha256"] ==
            "a1313519c3f58216586b989d97e1c0c7c688ca059d81a5771d6d6e24574afd8b",
            "encrypted result digest mismatch")
    require((readback["original_bid_events"], readback["original_ask_events"],
             readback["original_quote_events"]) == (14003, 14209, 28212),
            "quote provenance event counts mismatch")
    require(decimal(readback["initial_eur"]) == Decimal("200"), "capital is not EUR200")
    cells = readback["risk_cells"]
    require(type(cells) is list and len(cells) == 6, "must contain six result rows")
    observed = {}
    for cell in cells:
        key = (decimal(cell["risk_fraction"]), decimal(cell["roundtrip_cost_reserve_eur"]))
        require(key in planned and key not in observed, "missing/duplicate/unregistered scenario")
        require(type(cell["modeled_entries"]) is int and type(cell["stop_risk_rejections"]) is int
                and cell["modeled_entries"] >= 0 and cell["stop_risk_rejections"] >= 0,
                "invalid entry or rejection count")
        observed[key] = (cell["modeled_entries"], cell["stop_risk_rejections"],
                         decimal(cell["hypothetical_final_equity_eur"]))
    require(set(observed) == planned, "incomplete preregistered Cartesian product")
    require(observed == EXPOSED, "post-result numeric receipt mismatch")
    # Importantly, conserving EUR200 through zero fills is *not* profitability.
    require(all(entries == 0 or end < Decimal("200")
                for entries, _rejections, end in observed.values()),
            "receipt purports unsupported positive executable economics")
    for key in ("hard21", "bidask_are_broker_fills", "scenario_units_are_broker_certified",
                "post_result_parameter_selection", "protected_forward_opened",
                "confirmation_opened", "canonical_V2_trial_ledger_modified",
                "owner_checkpoint_modified"):
        require(readback[key] is False, "forbidden claim or mutation: " + key)
    require(readback["full_iso_utc_weeks"] == 0 and readback["live_orders"] == 0
            and readback["broker_requests"] == 0,
            "false weekly coverage or real execution claim")
    require(readback["research_disposition"] == "NO_PROMOTION_NO_EXECUTABLE_EDGE",
            "positive selection is not supported")
    return {"validated_cells": len(observed), "complete_iso_weeks": 0,
            "classification": "EXPOSED_DEVELOPMENT_NO_PROMOTION"}

if __name__ == "__main__":
    print(json.dumps(validate(json.loads(RECEIPT.read_text()),
                              json.loads(PREREG.read_text())), sort_keys=True))
