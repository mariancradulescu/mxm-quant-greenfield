import hashlib
import json
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from discovery.canonical import verify_spec_hash
from discovery.ledger import read_ledger
from m6.session_replay import NY, NasdaqCashCalendar
from m7.competition_expansion_index_m15 import (
    CANDIDATE_HASHES,
    opening_range_breakout_intents,
    relative_value_intents,
    sign_replay_intents,
)

ROOT=Path(__file__).resolve().parents[1]

def load(rel):
    return json.loads((ROOT/rel).read_text(encoding="utf-8"))

def git_blob_sha1(rel):
    data=(ROOT/rel).read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii")+data).hexdigest()

def regular_rows(day, *, base=100.0, step=1.0):
    opened=datetime(day.year,day.month,day.day,9,30,tzinfo=NY).astimezone(timezone.utc)
    rows=[]
    for i in range(26):
        px=base+i*step
        rows.append({
            "time_utc":(opened+timedelta(minutes=15*i)).isoformat().replace("+00:00","Z"),
            "open":str(px),
            "high":str(px+0.5),
            "low":str(px-0.5),
            "close":str(px+0.25),
            "tick_volume":"1",
        })
    return rows

class CompetitionExpansionWave01FreezeTests(unittest.TestCase):
    def test_01_final_stage_b_closure_audit_passes_and_authorizes_only_expansion(self):
        a=load("data/POST_STAGE_B_FINAL_CLOSURE_INDEPENDENT_AUDIT_V1.json")
        self.assertEqual(a["status"],"PASS")
        self.assertEqual(a["audited_head"],"e5d30d86fe56f67643a61c89d0022f86e324547a")
        self.assertEqual(a["audited_exact_head_ci"]["run_id"],35633163921)
        self.assertEqual(a["audited_exact_head_ci"]["tests_passed"],556)
        self.assertEqual(a["findings"]["material_defects"],0)
        self.assertFalse(a["findings"]["stage_b_rerun_authorized"])
        self.assertFalse(a["findings"]["stage_b_economics_rerun"])
        self.assertTrue(a["findings"]["competition_performance_expansion_may_begin"])

    def test_02_wave_is_prospectively_frozen_without_own_outcomes(self):
        w=load("discovery/COMPETITION_PERFORMANCE_EXPANSION_WAVE_01_V1.json")
        self.assertEqual(w["status"],"FROZEN_BEFORE_C013_C016_ECONOMIC_OUTCOMES_PENDING_EXACT_HEAD_CI")
        self.assertEqual(w["candidate_ids"],["V2-C013","V2-C014","V2-C015","V2-C016"])
        self.assertTrue(w["no_grid"])
        self.assertFalse(w["candidate_own_outcomes_seen_before_freeze"])
        self.assertFalse(w["earlier_candidate_failure_rescue"])
        self.assertFalse(w["threshold_loosening_for_hard21"])
        self.assertEqual(w["accounting_at_freeze"]["v2_attempts_used"],2)
        self.assertEqual(w["accounting_at_freeze"]["v2_search_budget_remaining"],82)
        self.assertEqual(w["accounting_at_freeze"]["economic_outcomes_opened"],4)
        self.assertFalse(w["protected_evidence_opened"])

    def test_03_candidate_hashes_are_active_and_semantically_valid(self):
        ledger=read_ledger(ROOT/"discovery/ledger.jsonl")
        self.assertGreaterEqual(len(ledger),26)
        self.assertEqual(sum(e["entry_type"]=="RESULT_RECORDED" for e in ledger[:22]),2)
        tail=ledger[22:26]
        self.assertEqual([e["sequence"] for e in tail],[23,24,25,26])
        self.assertEqual([e["candidate_id"] for e in tail],["V2-C013","V2-C014","V2-C015","V2-C016"])
        for cid in CANDIDATE_HASHES:
            c=load(f"discovery/candidates/{cid}.json")
            verify_spec_hash(c)
            self.assertEqual(c["spec_hash"],CANDIDATE_HASHES[cid])
            self.assertTrue(c["provenance"]["frozen_before_own_economic_outcome"])
            self.assertFalse(c["provenance"]["selected_without_candidate_own_return_or_pnl"] is False)

    def test_04_cost_scope_is_candidate_independent_and_fail_closed(self):
        a=load("evidence/COMPETITION_EXPANSION_INDEX_M15_COST_AUTHORITY_V1.json")
        self.assertEqual(a["status"],"FROZEN_PRE_C013_C016_OUTCOME_CONSERVATIVE_BOUND_DISCOVERY_ONLY")
        self.assertEqual(a["scope"]["eligible_transaction_boundary_et"],"09:45_THROUGH_14:45_INCLUSIVE")
        self.assertEqual(a["scope"]["missing_required_evidence"],"COST_UNRESOLVED_FAIL_CLOSED")
        self.assertEqual(a["candidate_independent_sources"]["US500_M15_BOUNDARY_QUOTE_EVIDENCE_sha256"],"601eedcb147021fff54f4d3bd2a43d831c455a821ddafa01a0036afe5c5485d6")
        self.assertEqual(a["candidate_independent_sources"]["NAS100_GENERIC_BOUND_COST_SUPPORT_sha256"],"dd4f6be917773fc580d4725d7c30ef4aabd5ec4ce19a30fdced8c5a85f4bd999")
        self.assertTrue(all(v is False for v in a["candidate_inputs_used_for_this_scope_extension"].values()))
        self.assertEqual(a["certification_effect"],"NONE")

    def test_05_sign_continuation_and_reversal_are_causal_nonoverlapping_contrasts(self):
        cal=NasdaqCashCalendar([],[])
        rows=regular_rows(date(2026,9,14),base=100,step=1)
        a=sign_replay_intents(rows,cal,candidate_id="V2-C013",spec_hash=CANDIDATE_HASHES["V2-C013"],reverse=False)
        b=sign_replay_intents(rows,cal,candidate_id="V2-C014",spec_hash=CANDIDATE_HASHES["V2-C014"],reverse=True)
        self.assertGreater(len(a),0)
        self.assertEqual(len(a),len(b))
        self.assertTrue(all(x.direction=="LONG" for x in a))
        self.assertTrue(all(x.direction=="SHORT" for x in b))
        for intents in (a,b):
            for x,y in zip(intents,intents[1:]):
                self.assertLess(x.exit_utc,y.decision_utc)
            self.assertTrue(all(x.decision_utc==x.entry_utc for x in intents))
            self.assertTrue(all(x.entry_utc.astimezone(NY).hour < 15 for x in intents))
            self.assertTrue(all(x.exit_utc.astimezone(NY).hour < 15 for x in intents))

    def test_06_opening_range_breakout_is_at_most_one_trade_per_session(self):
        cal=NasdaqCashCalendar([],[])
        rows=regular_rows(date(2026,9,14),base=100,step=1)
        intents=opening_range_breakout_intents(rows,cal)
        self.assertEqual(len(intents),1)
        self.assertEqual(intents[0].direction,"LONG")

    def test_07_cross_index_relative_value_uses_only_synchronized_completed_state(self):
        cal=NasdaqCashCalendar([],[])
        us=regular_rows(date(2026,9,14),base=100,step=0.1)
        nas=regular_rows(date(2026,9,14),base=200,step=1.0)
        intents=relative_value_intents(us,nas,cal)
        self.assertGreater(len(intents),0)
        self.assertTrue(all(x.direction=="SHORT_NAS100" for x in intents))
        self.assertTrue(all(x.decision_utc==x.entry_utc for x in intents))

    def test_08_live_accounting_changes_only_structural_ledger_count_at_freeze(self):
        s=load("CURRENT_STATE.json")
        hist=s["competition_performance_expansion"]
        self.assertEqual(hist["economic_outcomes_opened"],4); self.assertEqual(hist["v2_attempts_used"],2); self.assertEqual(hist["v2_search_budget_remaining"],82)
        self.assertEqual(hist["accounting_snapshot_scope"],"HISTORICAL_BEFORE_ULTRA_FAST_C017_C020_OUTCOMES")
        self.assertEqual(s["current_config_stage_b_outcomes_opened"],2)
        self.assertGreaterEqual(s["economic_outcomes_opened"],10)
        self.assertGreaterEqual(s["v2_attempts_used"],8)
        self.assertEqual(s["v2_evaluated_identities"],s["v2_attempts_used"])
        self.assertEqual(s["v2_search_budget"],84)
        self.assertEqual(s["v2_search_budget_remaining"],84-s["v2_attempts_used"])
        self.assertGreaterEqual(s["discovery_ledger_entries"],39)
        self.assertEqual(s["discovery_result_recorded_entries"],s["v2_attempts_used"])
        self.assertFalse(s["protected_evidence_opened"])
        self.assertFalse(s["live_orders_authorized"])
        self.assertFalse(s["competition_start_authorized"])

    def test_09_accepted_stage_b_and_economic_input_blobs_remain_immutable(self):
        expected={
          "m6/results/V2-C006_STAGE_B_CURRENT_CONFIG_V1.json":"0234d84f09a168ff70da4c07b9ccde49159010fc",
          "m6/results/V2-C012_STAGE_B_CURRENT_CONFIG_V1.json":"8c3b1fcdad6b43fcfed2af0919f3ddffd3b541f7",
          "m6/results/STAGE_B_CURRENT_CONFIG_RUN_RECORD_V1.json":"04df816b7c460045808bba61ba2c7662566fef38",
          "discovery/candidates/V2-C006.json":"a5a6e4865206a0f85afcae28a65004e1e24a8277",
          "discovery/candidates/V2-C012.json":"a9a8464d9cf161c3dcae39536280089058e882d9",
          "evidence/TIER1_DISCOVERY_TRANSACTION_LOCAL_COST_RULE_V1.json":"64bc7a000e750cd29710b372c4e5587f1610668a",
          "evidence/M6_STAGE_B_HISTORICAL_MARGIN_AUTHORITY_RESOLUTION_V2.json":"63a959ef9c767956d92772102f3aae3ab3b58237",
          "evidence/M6_STAGE_B_CURRENT_BROKER_CONFIGURATION_AUTHORITY_V1.json":"47c1f081bdce0dec92dd40543d6627ae224f6f8d",
        }
        for path,sha in expected.items():
            self.assertEqual(git_blob_sha1(path),sha,path)

if __name__=="__main__":
    unittest.main(verbosity=2)
