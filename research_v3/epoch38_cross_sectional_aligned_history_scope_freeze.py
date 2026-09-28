"""Epoch38 deterministic aligned-history prerequisite validator.

This module validates the already-accepted semantic decision.  It does not fetch
market data, inspect predictive returns, compute PnL, or consume an economic attempt.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

PROPOSAL_REF = Path("research_v3/ai_director/proposals/AUTO_reason_9d1e673edc306eec9e7598261c9fe5e3.json")
PEER_INDEX_REF = Path("evidence/CROSS_SECTIONAL_PEER_COHORT_INDEX_V1.json")
FREEZE_REF = Path("research_v3/EPOCH38_CROSS_SECTIONAL_ALIGNED_HISTORY_SCOPE_FREEZE_V1.json")
READINESS_REF = Path("research_v3/EPOCH38_CROSS_SECTIONAL_ALIGNED_HISTORY_ACQUISITION_READINESS_V1.json")
PEER_ID = "peer_f00b1cfa2c5c4549"
EXPECTED_BREADTH = 113
EXPECTED_UNKNOWN = 112
EXPECTED_ACCEPTED_HISTORY = 1
EXPECTED_SAMPLE = 48
EXPECTED_PROPOSAL_BLOB_SHA = "745fcbd8c6f7532a7cdd5c5ae59ca6487f61ff6f"
EXPECTED_PROPOSAL_FILE_SHA256 = "5cf3d23355ade0ccc79e1e8fcd103c538cc76e36b21c5c7d354b9ba59b735cd2"

class Epoch38ScopeError(ValueError):
    pass

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _load(root: Path, rel: Path) -> dict[str, Any]:
    value=json.loads((root/rel).read_text(encoding="utf-8"))
    if not isinstance(value,dict):
        raise Epoch38ScopeError(f"expected JSON object: {rel}")
    return value

def _cohort(index: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows=[dict(x) for x in index.get("identities",[]) if x.get("peer_candidate_cohort_id")==PEER_ID]
    if len(rows)!=EXPECTED_BREADTH:
        raise Epoch38ScopeError("accepted peer-cohort breadth mismatch")
    accepted=[x for x in rows if x.get("accepted_history_state")=="ACCEPTED_HISTORY_AVAILABLE"]
    unknown=[x for x in rows if x.get("accepted_history_state")=="UNKNOWN"]
    if len(accepted)!=EXPECTED_ACCEPTED_HISTORY or len(unknown)!=EXPECTED_UNKNOWN:
        raise Epoch38ScopeError("accepted peer-cohort history-state partition mismatch")
    if accepted[0].get("broker_symbol")!="NIO.US-24":
        raise Epoch38ScopeError("accepted reusable-history member mismatch")
    expected_basis={
        "asset_class":"US Equities",
        "product_type":"EXTENDED_HOURS_SHARE_CFD",
        "session_regions":"ASIA|EUROPE|US",
        "coverage_bucket":"NEAR_24X5_MULTI_SESSION_SCHEDULE",
    }
    if any(x.get("peer_coherence_metadata")!=expected_basis for x in rows):
        raise Epoch38ScopeError("accepted peer-cohort coherence basis mismatch")
    return rows

def derive_symbols(index: Mapping[str, Any]) -> list[str]:
    rows=_cohort(index)
    unknown=[x for x in rows if x.get("accepted_history_state")=="UNKNOWN"]
    unknown.sort(key=lambda x:(-float(x["capital_efficiency_proxy_schedule_minutes_per_minimum_margin_eur"]),str(x["broker_symbol"])))
    if len(unknown)!=112:
        raise Epoch38ScopeError("unknown-history cohort breadth mismatch")
    selected:list[str]=[]
    for stratum in range(4):
        block=unknown[stratum*28:(stratum+1)*28]
        if len(block)!=28:
            raise Epoch38ScopeError("selection stratum breadth mismatch")
        for k in range(12):
            selected.append(str(block[int((k+0.5)*len(block)//12)]["broker_symbol"]))
    if len(selected)!=EXPECTED_SAMPLE or len(set(selected))!=EXPECTED_SAMPLE:
        raise Epoch38ScopeError("prospective sample cardinality mismatch")
    return selected

def validate_documents(
    proposal: Mapping[str, Any],
    index: Mapping[str, Any],
    freeze: Mapping[str, Any],
    *,
    proposal_git_blob_sha: str = EXPECTED_PROPOSAL_BLOB_SHA,
    proposal_file_sha256: str = EXPECTED_PROPOSAL_FILE_SHA256,
) -> dict[str, Any]:
    if proposal_git_blob_sha!=EXPECTED_PROPOSAL_BLOB_SHA:
        raise Epoch38ScopeError("accepted proposal file binding mismatch")
    if proposal_file_sha256!=EXPECTED_PROPOSAL_FILE_SHA256:
        raise Epoch38ScopeError("accepted proposal SHA-256 binding mismatch")
    src=freeze.get("source_ai_proposal") or {}
    if (src.get("proposal_ref")!=str(PROPOSAL_REF)
            or src.get("proposal_git_blob_sha")!=EXPECTED_PROPOSAL_BLOB_SHA
            or src.get("accepted_proposal_file_sha256")!=EXPECTED_PROPOSAL_FILE_SHA256
            or src.get("accepted_proposal_hash")!="d0f9945e61b6c400d34816b1b899894377541f357f5d0a108eb8c1d1ee8fd2b4"
            or src.get("accepted_operation_id")!="op_d6d8c4a72c94795fef1428aa4db6a0da"):
        raise Epoch38ScopeError("freeze is not bound to the exact accepted proposal file")
    if freeze.get("schema")!="mxm.greenfield.epoch38-cross-sectional-aligned-history-scope-freeze.v1" or freeze.get("status")!="FROZEN_NON_ECONOMIC_PREREQUISITE":
        raise Epoch38ScopeError("unsupported or unfrozen Epoch38 prerequisite")
    decision=proposal.get("decision") or {}
    scope=decision.get("scope") or {}
    methodology=decision.get("universe_methodology") or {}
    if proposal.get("proposal_id")!="post_index_extended_hours_cross_sectional_alignment_v1":
        raise Epoch38ScopeError("accepted proposal identity mismatch")
    if methodology.get("source_peer_cohort_id")!=PEER_ID or methodology.get("source_peer_cohort_breadth")!=EXPECTED_BREADTH:
        raise Epoch38ScopeError("accepted proposal peer-cohort binding mismatch")
    peer_rows=_cohort(index)
    if (freeze.get("source_peer_index_ref")!=str(PEER_INDEX_REF)
            or (freeze.get("source_peer_cohort") or {}).get("peer_candidate_cohort_id")!=PEER_ID
            or (freeze.get("source_peer_cohort") or {}).get("accepted_breadth")!=EXPECTED_BREADTH):
        raise Epoch38ScopeError("freeze peer-index or cohort binding mismatch")
    peer_symbols={str(x["broker_symbol"]) for x in peer_rows}
    frozen_symbols=list((freeze.get("selection") or {}).get("exact_symbols") or [])
    if len(frozen_symbols)!=EXPECTED_SAMPLE or len(set(frozen_symbols))!=EXPECTED_SAMPLE:
        raise Epoch38ScopeError("frozen sample cardinality mismatch")
    outside=[s for s in frozen_symbols if s not in peer_symbols]
    if outside:
        raise Epoch38ScopeError("frozen symbol outside the accepted peer cohort: "+",".join(outside[:3]))
    proposed=list(scope.get("exact_symbols") or [])
    if frozen_symbols!=proposed:
        raise Epoch38ScopeError("frozen exact symbol scope drifted from accepted proposal")
    recomputed=derive_symbols(index)
    if frozen_symbols!=recomputed:
        raise Epoch38ScopeError("frozen symbols do not match prospective outcome-blind selection law")
    if ((freeze.get("selection") or {}).get("exact_symbol_count")!=EXPECTED_SAMPLE
            or (freeze.get("source_peer_cohort") or {}).get("accepted_history_available_count")!=EXPECTED_ACCEPTED_HISTORY
            or (freeze.get("source_peer_cohort") or {}).get("accepted_history_symbol")!="NIO.US-24"
            or (freeze.get("source_peer_cohort") or {}).get("unknown_history_count")!=EXPECTED_UNKNOWN):
        raise Epoch38ScopeError("frozen peer-cohort history partition or sample count drift")
    dev=freeze.get("development_data") or {}
    pdev=scope.get("development_interval") or {}
    if dev.get("resolution")!="M5" or scope.get("resolution")!="M5":
        raise Epoch38ScopeError("resolution drift")
    if dev.get("interval")!={"start_utc":"2026-02-02T00:00:00Z","end_utc":"2026-09-13T23:59:59Z","weeks":32}:
        raise Epoch38ScopeError("development interval drift")
    if pdev!=dev.get("interval"):
        raise Epoch38ScopeError("development interval differs from accepted proposal")
    if (dev.get("protected_forward_excluded") is not True
            or dev.get("reuse_valid_development_bytes") is not True
            or dev.get("recapture_valid_covered_bytes") is not False
            or dev.get("market_data_fetch_authorized_by_this_freeze") is not False):
        raise Epoch38ScopeError("development-data reuse, recapture, or acquisition boundary drift")
    if (freeze.get("selection") or {}).get("outcome_blind") is not True:
        raise Epoch38ScopeError("selection must remain outcome blind")
    if (freeze.get("selection") or {}).get("strata")!=scope.get("selection_strata"):
        raise Epoch38ScopeError("selection strata differ from accepted proposal")
    estimand=freeze.get("prerequisite_estimand") or {}
    design=decision.get("estimand_design") or {}
    if (estimand.get("predictive_outcome_opened") is not False
            or estimand.get("economic_outcome_opened") is not False
            or estimand.get("temporal_cluster_unit")!="UTC_TRADING_DATE"
            or estimand.get("effective_cross_sectional_breadth")!="DEPENDENCE_AWARE_PARTICIPATION_RATIO_EIGENVALUE"
            or estimand.get("report_raw_and_effective_breadth_separately") is not True
            or estimand.get("immediate_non_predictive_estimand")!=design.get("immediate_non_predictive_estimand")):
        raise Epoch38ScopeError("non-predictive prerequisite estimand drift")
    if (scope.get("economic_outcome_opened") is not False
            or scope.get("predictive_strategy_outcome_opened") is not False
            or scope.get("protected_forward_excluded") is not True
            or scope.get("peer_candidate_cohort_id")!=PEER_ID):
        raise Epoch38ScopeError("accepted proposal outcome or protected-forward boundary drift")
    proposal_power=design.get("power_target") or {}
    gates=freeze.get("gates") or {}
    expected_power={
        "minimum_effective_independent_utc_days":proposal_power.get("minimum_effective_independent_utc_days"),
        "design_target_effective_days":proposal_power.get("design_target_effective_days"),
        "alpha_one_sided":proposal_power.get("alpha_one_sided"),
        "target_power":proposal_power.get("target_power"),
        "economically_interesting_standardized_daily_effect":proposal_power.get("economically_interesting_standardized_daily_effect"),
    }
    if any(gates.get(key)!=value for key,value in expected_power.items()):
        raise Epoch38ScopeError("effective-N or power-plan drift")
    if (gates.get("minimum_schedule_adjusted_coverage")!=0.95
            or gates.get("minimum_symbols_meeting_coverage")!=36
            or gates.get("chronology_conflicts_required")!=0
            or gates.get("minimum_median_effective_cross_sectional_breadth")!=20):
        raise Epoch38ScopeError("alignment or coherence gate drift")
    insufficiency=freeze.get("insufficiency_rule") or {}
    if (insufficiency.get("action")!="PROSPECTIVE_EXTENSION_OR_ESTIMAND_REDESIGN"
            or insufficiency.get("history_extension_increment_weeks")!=4
            or insufficiency.get("family_failure_authority") is not False):
        raise Epoch38ScopeError("insufficiency rule drift")
    if (freeze.get("interpretation_boundary") or {}).get("economic_outcome_authorized") is not False:
        raise Epoch38ScopeError("freeze cannot authorize economics")
    if (freeze.get("interpretation_boundary") or {}).get("family_exhaustion_authority") is not False:
        raise Epoch38ScopeError("prerequisite freeze cannot exhaust a family")
    boundary=freeze.get("interpretation_boundary") or {}
    if (boundary.get("predictive_strategy_outcome_authorized") is not False
            or boundary.get("protected_forward_opened") is not False
            or boundary.get("v2_attempt_consumed")!=0
            or boundary.get("economic_outcomes_opened_delta")!=0):
        raise Epoch38ScopeError("economic, protected-forward, or accounting boundary drift")
    return {
        "schema":"mxm.greenfield.epoch38-cross-sectional-aligned-history-acquisition-readiness.v1",
        "status":"READY_FOR_FRESH_SEMANTIC_ACQUISITION_DECISION",
        "freeze_ref":str(FREEZE_REF),
        "peer_candidate_cohort_id":PEER_ID,
        "accepted_peer_breadth":EXPECTED_BREADTH,
        "frozen_sample_size":EXPECTED_SAMPLE,
        "exact_symbols":frozen_symbols,
        "resolution":"M5",
        "development_interval":dev["interval"],
        "market_data_fetched":False,
        "predictive_outcome_opened":False,
        "economic_outcome_opened":False,
        "v2_attempts_consumed":0,
        "next_boundary":"Fresh semantic reasoning may authorize a machine-owned acquisition operation; this validator itself does not acquire data."
    }

def validate_root(root_value: str | Path=".") -> dict[str, Any]:
    root=Path(root_value).resolve()
    proposal=_load(root,PROPOSAL_REF)
    index=_load(root,PEER_INDEX_REF)
    freeze=_load(root,FREEZE_REF)
    return validate_documents(
        proposal,
        index,
        freeze,
        proposal_file_sha256=sha256_file(root/PROPOSAL_REF),
    )

def emit_readiness(root_value: str | Path=".") -> dict[str, Any]:
    root=Path(root_value).resolve()
    result=validate_root(root)
    READINESS_REF.parent.mkdir(parents=True,exist_ok=True)
    READINESS_REF.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return result
