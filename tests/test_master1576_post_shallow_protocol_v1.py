"""Offline governance/binding checks only. Never loads shallow ciphertext or rows."""
import hashlib
import json
import socket
import subprocess
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
S = 'research_core_v4/state/'
BASE = 'c611a7a38a74c79461b233b381b43328e715ba2a'
A = S+'BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_FINAL_CAMPAIGN_INDEPENDENT_ACCEPTANCE_AUTHORITY_V1.json'
P = S+'MASTER1576_POST_SHALLOW_OUTCOME_BLIND_DEEP_HISTORICAL_M5_QUALIFICATION_PROTOCOL_V1.json'
NEXT = 'PENDING_INDEPENDENT_AUDIT_OF_MASTER1576_POST_SHALLOW_OUTCOME_BLIND_QUALIFICATION_PROTOCOL_BEFORE_DECRYPTION_OR_SCREEN_EXECUTION'
STATES = [S+'V4_STATE.json', 'adaptive_competition/state/ADAPTIVE_COMPETITION_CURRENT_STATE.json', 'adaptive_competition/state/ADAPTIVE_COMPETITION_AUTHORITY_V1.json']
def load(p): return json.loads((ROOT/p).read_text())
def digest(p): return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT)
def bound(b):
    assert digest(b['ref']) == b['sha256'], b['ref']
def denied(*args,**kwargs): raise AssertionError('Network prohibited in offline validation')
class ProtocolAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_socket=socket.socket; socket.socket=denied
        cls.a=load(A);cls.p=load(P);cls.f=load(cls.a['final_manifest']['ref'])
    @classmethod
    def tearDownClass(cls): socket.socket=cls.original_socket
    def test_01_exact_manifest(self):
        b=self.a['final_manifest'];bound(b)
        self.assertEqual(b['commit'],BASE);self.assertEqual(b['exact_bytes'],110876)
        self.assertEqual(b['sha256'],'cc28c61a7788fc9d18bd54a343bc0e2c7467b27f1dbb111bf54185f9f0f16cb4')
        self.assertEqual(self.f['status'],'COMPLETE')
    def test_02_four_exact_segment_blobs(self):
        blobs=['1adc2e01e41f9afd1783971dde2e02e202526aad','2dd8cbe946f010c6e7e689dd6bd8f6d274e70ae4','6e4291d28f3e3aa18a641f6244e0fd8011286b38','06329d6435102491ee9fb7b4d22133b80aada8e2'];entries=[]
        for b,expected in zip(self.a['segment_manifests'],blobs):
            bound(b);self.assertEqual(b['blob_sha'],expected)
            self.assertEqual(git('hash-object',b['ref']).decode().strip(),expected)
            d=load(b['ref']);self.assertEqual(d['status'],'COMPLETE');self.assertEqual(len(d['entries']),25);entries+=d['entries']
        self.assertEqual(entries,self.f['entries'])
    def test_03_complete_master_coverage(self):
        master=load(self.p['sources']['MASTER']['ref']);self.assertEqual(len(master),1576)
        self.assertEqual(len({r['symbol_id'] for r in master}),1576)
        canon=json.dumps(master,sort_keys=True,separators=(',',':')).encode()
        self.assertEqual(hashlib.sha256(canon).hexdigest(),self.a['master1576_sha256'])
        for segment in range(1,5):
            ee=[e for e in self.f['entries'] if e['SEGMENT_INDEX']==segment]; ordinals=[]
            self.assertEqual([e['SHARD_INDEX'] for e in ee],list(range(25)))
            for e in ee:
                lo,hi=e['IDENTITY_RANGE'];ordinals.extend(range(lo,hi+1));self.assertEqual(e['REQUEST_COUNT'],hi-lo+1)
            self.assertEqual(ordinals,list(range(1,1577)))
    def test_04_exact_total_rows_and_requests(self):
        self.assertEqual(sum(e['ROW_COUNT'] for e in self.f['entries']),3355389)
        self.assertEqual(sum(e['REQUEST_COUNT'] for e in self.f['entries']),6304)
        self.assertEqual(self.a['totals']['canonical_M5_rows'],3355389)
        self.assertEqual(self.a['totals']['identity_segment_requests'],6304)
    def test_05_exact_asset_inventory(self):
        inv=self.a['exact_release_inventory'];assets=inv['assets'];self.assertEqual(len(assets),100)
        self.assertEqual(len({e['id'] for e in assets}),100);byname={e['name']:e for e in assets}
        self.assertEqual(set(byname),{e['ENCRYPTED_ASSET_NAME'] for e in self.f['entries']})
        self.assertEqual(inv['tag_name'],self.f['DURABLE_RELEASE_IDENTITY'])
        self.assertEqual(inv['body']['ARM_COMMIT'],self.f['ARM_COMMIT'])
        for e in self.f['entries']:
            a=byname[e['ENCRYPTED_ASSET_NAME']];self.assertEqual(a['digest'],'sha256:'+e['ENCRYPTED_ASSET_SHA256']);self.assertGreater(a['size'],0);self.assertEqual(a['state'],'uploaded')
    def test_06_zero_failure_and_protected_rows(self):
        for e in self.f['entries']:
            for k in ['RETRY_COUNT','PAGE_CAP_HITS','PROTECTED_FORWARD_ROW_COUNT']:self.assertEqual(e[k],0)
            self.assertEqual(e['FAILURE_LEDGER'],{})
    def test_07_publication_only_recovery(self):
        d=self.a['publication_only_recovery'];self.assertEqual(d['commit'],BASE)
        self.assertEqual(git('rev-parse',BASE+'^').decode().strip(),d['parent'])
        self.assertEqual(git('diff-tree','--no-commit-id','--name-only','-r',BASE).decode().splitlines(),[self.a['final_manifest']['ref']])
        self.assertEqual(self.a['historical_run_failure']['run_id'],37567023127)
        self.assertEqual(self.a['historical_run_failure']['classification'],'POST_ACQUISITION_PUBLICATION_ONLY_FAILURE')
    def test_08_source_authorities_unchanged(self):
        for b in self.p['sources'].values():
            bound(b);self.assertEqual((ROOT/b['ref']).read_bytes(),git('show',BASE+':'+b['ref']))
        self.assertEqual(self.p['sources']['DISCOVERY']['sha256'],'ce80c4a71fe2f49c3f9b6eba7797f47de6e2f49827bd97384e54b81e63f28be5')
    def test_09_primary145_preserved(self):
        d=load(self.p['sources']['PRIMARY145']['ref']);self.assertEqual(d['primary_count'],145)
        self.assertEqual(sum(x['row_count'] for x in d['primary_series']),11406418)
        r=self.p['preservation']['PRIMARY145'];self.assertFalse(r['replace']);self.assertFalse(r['reinterpret']);self.assertFalse(r['disjoint_confirmation'])
    def test_10_no_data_threshold_fitting(self):
        g=self.p['threshold_governance'];self.assertFalse(g['data_tuned_thresholds']);self.assertFalse(g['resolve_by_inspecting_capture']);self.assertFalse(g['universal_absolute_row_count_floor'])
        for r in self.p['rules']:
            self.assertTrue(r['authorities'])
            for s in r['authorities']:self.assertIn(s['source'],self.p['sources'])
            for t in r['exact_thresholds']:self.assertTrue(t['justification'])
        ids={r['id']:r for r in self.p['rules']}
        for k in ['TEMPORAL','SEGMENT_PRESENCE','ACTIVITY','FRICTION','EUR200']:self.assertTrue(ids[k]['unresolved'])
        self.assertIn('Any UNRESOLVED mandatory criterion blocks QUALIFIED',self.p['future_classification']['qualified_law'])
    def test_11_no_top_k_or_duration(self):
        self.assertFalse(self.p['threshold_governance']['fixed_top_k']);self.assertFalse(self.p['future_classification']['truncate_to_top_k']);self.assertTrue(self.p['future_classification']['all_passers_remain_eligible'])
        d=self.p['deep_historical_M5'];self.assertFalse(d['authorized']);self.assertFalse(d['duration_selected']);self.assertIsNone(d['duration']);self.assertFalse(d['assume_years'])
    def test_12_all_states_bound_consistently(self):
        for path in STATES:
            d=load(path);self.assertEqual(d['current_authority'],A);self.assertEqual(d['current_authority_sha256'],digest(A));self.assertEqual(d['qualification_protocol_ref'],P);self.assertEqual(d['qualification_protocol_sha256'],digest(P));self.assertEqual(d['next_action'],NEXT)
            for k in ['current_next_action_type','current_operation']:
                if k in d:self.assertEqual(d[k],NEXT)
            key='shallow_m5_v2_current_operation' if path.endswith('V4_STATE.json') else 'shallow_m5_v2_operational_rebind';b=d[key]
            self.assertEqual(b['v4_production_run_count'],1);self.assertTrue(b['v4_campaign_complete']);self.assertFalse(b['active_capture_ARM_present']);self.assertFalse(b['decryption_authorized']);self.assertFalse(b['screen_execution_authorized']);self.assertTrue(b['historical_completed_V4_ARM_present'])
    def test_13_budget_and_closed_boundaries(self):
        expected={'total':84,'used':21,'remaining':63,'refunds':0,'economic_outcomes_opened':29}
        for path,key in [(STATES[1],'search_budget'),(STATES[2],'search_budget_after')]:
            d=load(path);self.assertEqual(d[key],expected);self.assertFalse(d['protected_forward_opened']);self.assertFalse(d['confirmation_opened'])
        p=self.p['preservation'];self.assertTrue(p['triad_v7_parked']);self.assertFalse(p['protected_forward_opened']);self.assertFalse(p['confirmation_opened']);self.assertEqual(p['search_budget']['consume_this_task'],0)
    def test_14_changes_allowlist(self):
        allowed={A,P,*STATES,'tests/test_master1576_post_shallow_protocol_v1.py','.github/workflows/master1576-post-shallow-protocol-v1-offline.yml'}
        changed=set(git('diff','--name-only',BASE).decode().splitlines());self.assertLessEqual(changed,allowed)
        untracked=set(git('ls-files','--others','--exclude-standard').decode().splitlines());self.assertLessEqual(untracked,allowed)
    def test_15_no_broker_screen_or_decryption_entrypoint(self):
        b=self.p['execution_boundary'];self.assertTrue(all(v is False or v==0 for v in b.values()))
        self.assertFalse(self.p['future_step']['authorized_by_this_task'])
        workflow=(ROOT/'.github/workflows/master1576-post-shallow-protocol-v1-offline.yml').read_text()
        for forbidden in ['secrets.','workflow_dispatch','run-segment','decrypt','CTRADER_']:self.assertNotIn(forbidden,workflow)
        self.assertIn('ref: ${{ github.sha }}',workflow);self.assertIn('persist-credentials: false',workflow)
    def test_16_acquisition_not_information_result(self):
        self.assertEqual(self.a['interpretation'],'COMPLETE_BREADTH_FIRST_SHALLOW_M5_SUPPORT_CAPTURE_NOT_PREDICTIVE_OR_ECONOMIC_RESULT');self.assertEqual(self.p['status'],'FROZEN_PREOUTCOME_NOT_EXECUTED')
        self.assertTrue(self.p['future_classification']['nonqualified_is_not_null']);self.assertFalse(self.p['future_classification']['direct_candidate_promotion'])
    def test_17_protocol_acceptance_cross_binding(self):
        bound(self.p['campaign_acceptance']);self.assertEqual(self.a['next_action'],NEXT);self.assertEqual(self.p['next_action'],NEXT)
if __name__=='__main__':unittest.main()
