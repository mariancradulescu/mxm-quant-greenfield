"""Offline stage controller and exact-head validation; no selection beyond stage 1."""
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
from research_core_v4 import shared_baseline_campaign_v1 as b
from research_core_v4 import master1576_current_state_guard_v6 as g
ROOT=Path(__file__).resolve().parents[1]

def freeze_stage(root):
    root=Path(root);b.require(not (root/b.SPEC).exists(),'OUTPUT_ALREADY_PRESENT')
    trace=[];(root/b.PROTOCOL).parent.mkdir(parents=True,exist_ok=True)
    (root/b.PROTOCOL).write_bytes(b.canonical(b.protocol()));ph=g.sha(root,b.PROTOCOL);trace.append('PROTOCOL_FROZEN')
    reads=[];trace.append('TWO_INPUT_COMPARTMENT_OPENED');result=b.build_root(root,reads)
    b.require(g.sha(root,b.PROTOCOL)==ph,'PROTOCOL_CHANGED_DURING_EXECUTION');trace.append('NONUNIQUENESS_PROVED')
    (root/b.SPEC).write_bytes(b.canonical(result));trace.append('OUTPUT_FROZEN')
    return trace,reads

def main():
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if os.environ.get('GITHUB_SHA'):b.require(head==os.environ['GITHUB_SHA'],'EXACT_HEAD_DRIFT')
    suite=unittest.defaultTestLoader.loadTestsFromName('tests.test_shared_baseline_campaign_v1')
    with patch('socket.socket',side_effect=AssertionError('OFFLINE_NETWORK')),patch('urllib.request.urlopen',side_effect=AssertionError('OFFLINE_NETWORK')):
        r=unittest.TextTestRunner(verbosity=2).run(suite);reads=[];b.build_root(ROOT,reads);state=g.validate_root(ROOT)
    record={'schema':'mxm.v4.shared-baseline-campaign.exact-head-validation.v1','exact_validated_head':head,'run_id':os.environ.get('GITHUB_RUN_ID'),'run_attempt':os.environ.get('GITHUB_RUN_ATTEMPT'),
        'tests_passed':r.testsRun-len(r.failures)-len(r.errors)-len(r.skipped),'tests_failed':len(r.failures)+len(r.errors),'tests_skipped':len(r.skipped),
        'actual_baseline_builder_reads':reads,'baseline_read_allowlist':sorted(b.ALLOWED),'candidate_files_visible':False,
        'historical_outcome_files_read_by_baseline_builder':0,'candidate_rebuild_executed':False,'functional_reapplication_executed':False,
        'functional_byte_exact':True,'network_blocked':True,'market_routes':0,'market_rows_used':0,'broker_contacts':0,'power_trials':0,'duration_selected':False,'new_economic_outcomes':0,
        'boundary_kind':'NONDEFENSIBLE_FREE_DESIGN_CHOICE_STAGE_1_STOP','state':state}
    print('SHARED_BASELINE_CAMPAIGN_VALIDATION='+json.dumps(record,sort_keys=True));return 0 if r.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())
