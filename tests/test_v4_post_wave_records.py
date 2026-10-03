import gzip,hashlib,json,pathlib,unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
def read(n):return json.loads((ROOT/'research_core_v4/state'/n).read_bytes())
class PostWaveRecordChecks(unittest.TestCase):
    def test_original_raw_and_interpretation_bytes(self):
        for n,h in [('FIRST_V4_DEVELOPMENT_RESPONSE_RESULT_V1.json','77462da0329b21dd981896c3ab31f3383ef8f092948ac1c6c61a6c148e630208'),('FIRST_V4_DEVELOPMENT_RESPONSE_INTERPRETATION_V1.json','715e0d100fddda9b525fedc6f1dbf852973419d14634fa0c347fdb445d31cad2')]:
            self.assertEqual(hashlib.sha256((ROOT/'research_core_v4/state'/n).read_bytes()).hexdigest(),h)
    def test_49_old_closure_nodes_not_reclassified(self):
        old=read('V3_CLOSURE_DEPENDENCY_GRAPH_V1.json');new=read('POST_FIRST_V4_CLOSURE_LEDGER_V1.json')
        self.assertEqual(new['nodes'][:49],old['nodes']);self.assertEqual(len(new['nodes']),50)
        self.assertFalse(new['nodes'][-1]['broader_concept_closed'])
        self.assertEqual(new['nodes'][-1]['small_or_sparse_effects'],'LOW_POWER_INCONCLUSIVE_NOT_GLOBAL_NULL')
    def test_single_source_and_no_leaf_selection_inputs(self):
        sel=read('NEXT_INFORMATION_SOURCE_SELECTION_V1.json');self.assertEqual(sum(r['selected'] for r in sel['ranked_mechanisms']),1)
        self.assertEqual(len(sel['ranked_mechanisms']),12)
        self.assertEqual(set(sel['allowed_first_wave_input']),{'exact_wave_failed_to_advance','exact_closure_scope'})
        self.assertEqual(sel['selected_source'],'TOP_OF_BOOK_QUOTE_STATE')
    def test_full_1576_inventory_not_41_panel_universe(self):
        x=json.loads(gzip.decompress((ROOT/'research_core_v3/state/ACCEPTED_DATA_QUALITY_TABLE_V1.json.gz').read_bytes()))
        c=read('POST_FIRST_V4_PROJECT_COVERAGE_REFRESH_V1.json')
        self.assertEqual(len(x['rows']),1576);self.assertEqual(sum(c['asset_class_identity_counts'].values()),1576)
        self.assertTrue(c['structural_41_representatives_are_not_the_universe'])
    def test_bound_records_and_actual_synthetic_environment_not_market_certified(self):
        audit=read('NEXT_QUOTE_SEQUENCE_PREPARATION_AUDIT_V1.json')
        for p,h in audit['record_and_scaffolding_sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT/p).read_bytes()).hexdigest(),h,p)
        self.assertFalse(audit['response_execution_ready']);self.assertFalse(audit['acquisition_authorized'])
        cal=read('NEXT_QUOTE_SEQUENCE_SYNTHETIC_CALIBRATION_V1.json')
        self.assertFalse(cal['production_calibration_accepted']);self.assertFalse(cal['new_response_execution_ready'])
        self.assertTrue(all(not r['full_development_lead_power_measured'] for r in cal['synthetic_scenarios']))
    def test_all_900_exact_planned_request_rows(self):
        from research_core_v4.quote_sequence_preparation_v1 import request_manifest
        d=read('NEXT_QUOTE_SEQUENCE_DESIGN_V1.json');m=read('NEXT_QUOTE_SEQUENCE_REQUEST_MANIFEST_V1.json')
        expanded=[dict(zip(m['columns'],row)) for row in m['rows']]
        self.assertEqual(expanded,request_manifest(d));self.assertEqual(len(expanded),900)
        self.assertEqual(m['status'],'PLANNED_ONLY_NO_REQUESTS_SENT')
    def test_state_boundaries_and_legacy_freeze(self):
        s=read('V4_STATE.json');self.assertEqual(s['recovery_v4_preparation']['accepted_canonical_result_count'],1)
        self.assertEqual(s['governance']['candidate_frozen_count'],0);self.assertFalse(s['governance']['protected_forward_opened'])
        self.assertFalse(s['first_wave']['confirmation_outcomes_opened']);self.assertFalse(s['governance']['quote_revision_v2_execution_authorized'])
        for key in ['response_execution_authorized','broker_acquisition_authorized','ARM_present','attempt_lock_present','canonical_result_present']:
            self.assertFalse(s['next_prospective_wave'][key])
        frozen=json.loads((ROOT/'research_core_v3/state/V3_FREEZE_AUTHORITY_V1.json').read_bytes())
        self.assertEqual(frozen['quote_revision_v2']['research_execution_status'],'HELD_PENDING_V4')

if __name__=='__main__':unittest.main()
