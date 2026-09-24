import json, tempfile, unittest, zipfile, csv, io
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch

from discovery.canonical import verify_spec_hash
from m7.competition_performance_v3_c032_evaluator import event_direction,build_admitted_trades,C032PreOutcomeCostUnresolved
from research_v3.c032_execute import C032ExecutionNotAuthorized,execute_authorized

ROOT=Path(__file__).resolve().parents[1]
CID="V2-C032"
SPEC_HASH="96a752ab7c91401f569527b0a21c7757e4418002cc918e0663589e6ae4044936"

def bar(t,o,h,l,c): return {"t":t,"o":o,"h":h,"l":l,"c":c,"v":1}

class C032ControlTests(unittest.TestCase):
    def test_spec_hash_and_causality(self):
        spec=json.loads((ROOT/"discovery/candidates/V2-C032.json").read_text())
        self.assertTrue(verify_spec_hash(spec)); self.assertEqual(spec["spec_hash"],SPEC_HASH)
        self.assertTrue(spec["causal_availability"]["future_information_forbidden"])
        self.assertFalse(spec["position_admission_policy"]["future_entry_or_exit_availability_may_affect_signal_admission"])
        self.assertFalse(spec["position_admission_policy"]["same_symbol_overlap"])
        self.assertTrue(spec["provenance"]["frozen_before_own_economic_outcome"])

    def test_no_overlap_is_prior_active_state_not_cost_filter(self):
        st=datetime(2026,9,14,13,0,tzinfo=timezone.utc)
        rows=[]
        for i in range(24): rows.append(bar(st+i*timedelta(minutes=5),100,101,99,100))
        rows.append(bar(st+24*timedelta(minutes=5),100,104,99,103))
        for k in range(1,9): rows.append(bar(st+(24+k)*timedelta(minutes=5),103,104,102,103))
        # create second event ten minutes later; it must be suppressed while first trade is active
        rows[26]=bar(rows[26]["t"],103,107,102,106)
        events=[i for i in range(24,len(rows)) if event_direction(rows,i)]
        costs={}
        for i in events:
            t=rows[i]["t"]
            costs[t]={"event_bar_time_utc":t.isoformat().replace('+00:00','Z'),"entry_boundary_utc":(t+timedelta(minutes=5)).isoformat().replace('+00:00','Z'),"exit_boundary_utc":(t+timedelta(minutes=35)).isoformat().replace('+00:00','Z'),"entry_spread":0.2,"exit_spread":0.2,"entry_one_side_commission_price_equivalent":0.0,"exit_one_side_commission_price_equivalent":0.0,"roundtrip_cost_price_equivalent":0.2,"cost_state":"TRANSACTION_LOCAL_COST_RESOLVED"}
        trades,diag=build_admitted_trades(rows,costs)
        self.assertGreaterEqual(diag["events_detected"],2)
        self.assertGreaterEqual(diag["suppressed_by_prior_active_state"],1)
        self.assertEqual(len(trades),diag["admitted"])

    def test_admitted_unresolved_cost_halts_before_result(self):
        st=datetime(2026,9,14,13,0,tzinfo=timezone.utc)
        rows=[bar(st+i*timedelta(minutes=5),100,101,99,100) for i in range(24)]
        rows.append(bar(st+120*timedelta(minutes=1),100,104,99,103))
        for k in range(1,8): rows.append(bar(st+(24+k)*timedelta(minutes=5),103,104,102,103))
        t=rows[24]["t"]
        costs={t:{"event_bar_time_utc":t.isoformat().replace('+00:00','Z'),"entry_boundary_utc":(t+timedelta(minutes=5)).isoformat().replace('+00:00','Z'),"exit_boundary_utc":(t+timedelta(minutes=35)).isoformat().replace('+00:00','Z'),"entry_spread":0.2,"exit_spread":None,"entry_one_side_commission_price_equivalent":0.0,"exit_one_side_commission_price_equivalent":None,"roundtrip_cost_price_equivalent":None,"cost_state":"COST_UNRESOLVED"}}
        with self.assertRaises(C032PreOutcomeCostUnresolved): build_admitted_trades(rows,costs)

    def test_wrong_head_rejects_before_economics(self):
        with patch("research_v3.c032_execute.evaluate",side_effect=AssertionError("economics must not run")) as economic:
            with self.assertRaises(C032ExecutionNotAuthorized): execute_authorized(ROOT,"missing.zip",execution_head="0"*40,execution_ci_run_id=0)
            economic.assert_not_called()

if __name__=="__main__": unittest.main(verbosity=2)
