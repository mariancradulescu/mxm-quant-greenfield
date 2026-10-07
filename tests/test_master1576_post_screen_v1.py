"""Exact post-screen accounting and explicit unresolved design/power boundary."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from research_core_v4 import master1576_post_screen_v1 as p
ROOT=Path(__file__).resolve().parents[1]
class PostScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r=p.read(ROOT,p.RESULT);cls.a={x:p.read(ROOT,x) for x in [p.ACCEPT,p.SUMMARY,p.ROSTER,p.DESIGN,p.POWER]}
    def test_01_exact_result_hash_bytes_schema(self):
        b=(ROOT/p.RESULT).read_bytes();self.assertEqual(p.sha(b),p.HASH);self.assertEqual(len(b),3192310)
        from research_core_v4.master1576_screen_v2 import validate_output
        validate_output(self.r)
    def test_02_all1576_identity_and_order_binding(self):
        proto=p.read(ROOT,p.PROTO);master=p.read(ROOT,proto['bindings']['master']['ref'])
        self.assertEqual([(x['MASTER_ORDINAL'],x['SYMBOL_ID'],x['BROKER_NATIVE_CONTEXT']) for x in self.r['identities']],[(i,x['symbol_id'],x['asset_class']) for i,x in enumerate(master,1)])
    def test_03_complete_100_assets_rows(self):
        self.assertEqual(self.r['processed_asset_count'],100);self.assertEqual(self.r['processed_canonical_row_count'],3355389);self.assertEqual(sum(x['TOTAL_ROW_COUNT'] for x in self.r['identities']),3355389)
    def test_04_exact_all_passers_roster(self):
        entries=self.a[p.ROSTER]['entries'];self.assertEqual(len(entries),1575)
        expected=[{k:x[k] for k in ['MASTER_ORDINAL','SYMBOL_ID','BROKER_NATIVE_CONTEXT']} for x in self.r['identities'] if x['COMPLETE_REASON_LEDGER']['hard_gates_pass']]
        self.assertEqual(entries,expected);self.assertTrue(all(set(x)=={'MASTER_ORDINAL','SYMBOL_ID','BROKER_NATIVE_CONTEXT'} for x in entries))
    def test_05_exact_support_limited_reason(self):
        records=self.a[p.SUMMARY]['support_limited_records'];self.assertEqual(len(records),1);r=records[0]
        self.assertEqual((r['MASTER_ORDINAL'],r['SYMBOL_ID'],r['BROKER_NATIVE_CONTEXT']),(515,3741,'AU Equities'));self.assertEqual(r['TOTAL_ROW_COUNT'],0);self.assertEqual(r['ROW_COUNT_BY_SEGMENT'],[0]*4)
        self.assertIn('ZERO_AUTHENTIC_ROWS',r['COMPLETE_REASON_LEDGER']['codes']);self.assertFalse(r['COMPLETE_REASON_LEDGER']['late_start_proven'])
    def test_06_global_context_accounting(self):
        s=self.a[p.SUMMARY];c=list(s['by_broker_native_context'].values());self.assertEqual(len(c),29)
        self.assertEqual(sum(x['identity_count'] for x in c),1576);self.assertEqual(sum(x['eligible_count'] for x in c),1575);self.assertEqual(sum(x['total_row_count'] for x in c),3355389)
        self.assertEqual(sum(s['global']['row_count_by_segment']),3355389)
    def test_07_active_days_not_independent_sample_size(self):
        s=self.a[p.SUMMARY]['global']['active_day_geometry'];self.assertEqual(s['identity_day_sum'],31332)
        self.assertIn('not unique calendar days',s['interpretation']);self.assertEqual(s['active_day_quantiles']['max'],28)
    def test_08_segment_presence_actual_geometry(self):
        s=self.a[p.SUMMARY]['global']['segment_presence_counts'];self.assertEqual(s['pattern_counts'],{'0000':1,'0011':1,'1111':1574});self.assertEqual(s['present_identity_count_by_segment'],[1574,1574,1575,1575])
    def test_09_gaps_preserved_as_descriptive(self):
        r=self.r['identities'];out=self.a[p.SUMMARY]['global']['gap_geometry']
        self.assertEqual(out['within_segment_interval_count'],sum(g['interval_count'] for x in r for g in x['OBSERVED_GAP_GEOMETRY']));self.assertEqual(sum(out['within_segment_histogram_minutes'].values()),out['within_segment_interval_count'])
        self.assertFalse(self.a[p.SUMMARY]['gap_gate'])
    def test_10_tick_volume_never_selection_gate(self):
        s=self.a[p.SUMMARY];tick=s['global']['tick_volume_descriptive'];self.assertEqual(tick['nonzero_tick_volume_count']+tick['zero_tick_volume_count'],3355389);self.assertFalse(s['activity_gate'])
        self.assertFalse(self.a[p.ROSTER]['fixed_top_k']);self.assertFalse(self.a[p.ROSTER]['ranking'])
    def test_11_deterministic_artifacts_roundtrip(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('No network')),patch('socket.socket',side_effect=AssertionError('No network')):
            a=p.build(ROOT);b=p.build(ROOT)
        for path,d in a.items():self.assertEqual(p.canonical(d),p.canonical(b[path]));self.assertEqual(p.canonical(d),(ROOT/path).read_bytes())
    def test_12_only_allowed_document_sources_read(self):
        allowed={p.RESULT,p.DISCOVERY,p.SELECTION,p.PROTO,p.PARK,p.FACTOR,p.PRIMARY,p.S+'INFORMATION_SOURCE_CATALOG_V1.json'};seen=[];original=Path.read_bytes
        def checked(path):
            relative=str(path.relative_to(ROOT));self.assertIn(relative,allowed);seen.append(relative);return original(path)
        with patch.object(Path,'read_bytes',checked):p.build(ROOT)
        self.assertNotIn('research_core_v4/asymmetric_recovery_v4_gate.py',seen)
    def test_13_tampered_result_rejected_before_derivation(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);f=root/p.RESULT;f.parent.mkdir(parents=True);f.write_bytes((ROOT/p.RESULT).read_bytes()+b' ')
            with self.assertRaises(AssertionError):p.build(root)
    def test_14_all_artifact_source_hash_bindings(self):
        for path in [p.ACCEPT,p.SUMMARY,p.ROSTER,p.DESIGN]:
            source=self.a[path].get('source',self.a[path].get('result'));self.assertEqual(source['sha256'],p.HASH)
        power=self.a[p.POWER]
        for b in power['input_bindings'].values():self.assertEqual(p.sha((ROOT/b['ref']).read_bytes()),b['sha256'])
    def test_15_design_explicitly_unresolved_not_claimed_complete(self):
        d=self.a[p.DESIGN];self.assertEqual(d['status'],'FROZEN_PREOUTCOME_NO_ACQUISITION')
        self.assertIsNone(d['selected_information_question']);self.assertIsNone(d['frozen_context_cohorts']);self.assertIsNone(d['frozen_horizon_family']);self.assertIsNone(d['frozen_feature_family']);self.assertFalse(d['acquisition_authorized'])
    def test_16_power_target_existing_authority_only(self):
        q=self.a[p.POWER];self.assertEqual(q['prospective_power_target']['minimum_power_lower_95_bound'],.8)
        self.assertIn('lower95bound>=.80',p.read(ROOT,p.DISCOVERY)['power']['discovery']);self.assertEqual(q['synthetic_power_trials'],0);self.assertFalse(q['calibration_completed']);self.assertTrue(q['calibration_explicitly_blocked'])
    def test_17_all_required_support_criteria_unresolved(self):
        q=self.a[p.POWER];self.assertEqual(len(q['must_determine']),6)
        for x in q['must_determine'].values():self.assertEqual(x['status'],'UNRESOLVED');self.assertIsNone(x['value']);self.assertTrue(x['reason'])
        self.assertIsNone(q['minimum_defensible_duration']);self.assertFalse(q['duration_selected'])
    def test_18_no_conditional_downstream_artifacts_or_arm(self):
        for name in ['DEEP_HISTORICAL_M5_DURATION_DECISION','DEEP_M5_EXISTING_COVERAGE_RECONCILIATION','DEEP_M5_MISSING_INTERVAL_MATRIX','DEEP_M5_ACQUISITION_DESIGN']:
            self.assertFalse((ROOT/(p.S+'MASTER1576_V2_'+name+'_V1.json')).exists())
    def test_19_immutable_scientific_governance(self):
        expected={p.DISCOVERY:'ce80c4a71fe2f49c3f9b6eba7797f47de6e2f49827bd97384e54b81e63f28be5',p.SELECTION:'f1a2ce55407351686588b7ef9f1af45f08c83d4340dd03df0ed24eddbceff449',p.PROTO:'25d8b45d97fe6302af96c603202cf0f68764e844312987e54d06621c09938a30',p.PRIMARY:'3f42fcad0e82b80d4f51bfab3a7faae11bf0b83dedd511826d68c308e34a7e02',p.PARK:'c519897953ad361d6949a76f14cb0e374705b1d296378179f58ac375daf34fd8'}
        for path,h in expected.items():self.assertEqual(p.sha((ROOT/path).read_bytes()),h)
        self.assertTrue(p.read(ROOT,p.PARK)['exact_v7_parked'])
    def test_20_canonical_state_authority_next_and_budget(self):
        h=p.sha((ROOT/p.ACCEPT).read_bytes())
        for path in [p.S+'V4_STATE.json','adaptive_competition/state/ADAPTIVE_COMPETITION_CURRENT_STATE.json','adaptive_competition/state/ADAPTIVE_COMPETITION_AUTHORITY_V1.json']:
            d=p.read(ROOT,path);self.assertEqual(d['current_authority'],p.ACCEPT);self.assertEqual(d['current_authority_sha256'],h);self.assertEqual(d['next_action'],p.NEXT)
            self.assertEqual(d['post_screen_breadth_to_depth']['search_budget_use'],0);self.assertFalse(d['post_screen_breadth_to_depth']['protected_forward_opened']);self.assertFalse(d['post_screen_breadth_to_depth']['confirmation_opened'])
            for b in d['post_screen_breadth_to_depth']['bindings'].values():self.assertEqual(p.sha((ROOT/b['ref']).read_bytes()),b['sha256'])
    def test_21_acceptance_binds_execution_claim(self):
        a=self.a[p.ACCEPT];self.assertEqual(a['real_execution']['run_id'],37582823762);self.assertEqual(a['real_execution']['job_id'],112666159207);self.assertEqual(a['real_execution']['run_attempt'],1)
        self.assertTrue(a['real_execution']['attempt_claim'].endswith(a['authorization']['commit']));self.assertEqual(a['result']['commit'],p.START)
    def test_22_no_new_workflow_secret_or_market_route(self):
        t=(ROOT/'.github/workflows/master1576-post-screen-offline.yml').read_text();self.assertNotIn('secrets.',t);self.assertNotIn('contents: write',t);self.assertNotIn('workflow'+'_dispatch',t)
        code=(ROOT/'research_core_v4/master1576_post_screen_v1.py').read_text();self.assertNotIn('download_asset(',code);self.assertNotIn('run_authorized(',code)
