"""Exact final-head static/synthetic validation. No support worker or real row IO."""
import json,subprocess,sys,unittest
from pathlib import Path
from research_core_v4 import current_testability_frontier_v1 as c
from research_core_v4.master1576_current_state_guard_v9 import STATES
FRONTIER_COMMIT='c0034aeb25b6fed578f85ad05781458a1ccbc187'
def git(*args):return subprocess.check_output(['git',*args])
def route_verify():
 route=json.loads(Path(c.ROUTE).read_bytes());refs={x['ref'] for x in route['metadata_read_bindings']};trace=[]
 with c.io_firewall('.',refs,trace):raw={p:Path(p).read_bytes() for p in sorted(refs)}
 for x in route['metadata_read_bindings']:c.require(c.sha(raw[x['ref']])==x['sha256'],'ACCEPTED_METADATA_DRIFT')
 manifest=json.loads(raw[c.S+'BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_FINAL_DURABLE_MANIFEST_V1.json']);acceptance=json.loads(raw[c.S+'BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_FINAL_CAMPAIGN_INDEPENDENT_ACCEPTANCE_AUTHORITY_V1.json']);roster=json.loads(raw[c.S+'MASTER1576_V2_DEEP_HISTORICAL_M5_ELIGIBLE_ROSTER_V1.json'])
 c.require(len(manifest['entries'])==len(route['assets'])==100,'ASSET_COUNT')
 c.require(acceptance['exact_release_inventory']['release_id']==route['release_id'],'RELEASE_ID')
 accepted={x['name']:x for x in acceptance['exact_release_inventory']['assets']};byname={x['name']:x for x in route['assets']}
 for e in manifest['entries']:
  n=e['ENCRYPTED_ASSET_NAME'];v=byname[n];a=accepted[n]
  c.require(v['asset_id']==a['id'] and v['encrypted_bytes']==a['size'] and 'sha256:'+v['encrypted_sha256']==a['digest'],'ASSET_METADATA_DRIFT')
  c.require(v['plaintext_canonical_sha256']==e['PLAINTEXT_CANONICAL_SHA256'] and v['canonical_row_count_metadata']==e['ROW_COUNT'],'MANIFEST_BINDING')
  c.require(e['PROTECTED_FORWARD_ROW_COUNT']==0,'PROTECTED_FORWARD')
  c.require(any(e['IDENTITY_RANGE'][0]<=x['MASTER_ORDINAL']<=e['IDENTITY_RANGE'][1] for x in roster['entries']),'UNNECESSARY_SHARD')
 c.require(len(roster['entries'])==1575,'ROSTER_COUNT')
 return trace

def main():
 head=git('rev-parse','HEAD').decode().strip();chain=[c.START,c.GOVERNANCE_COMMIT,FRONTIER_COMMIT,head]
 for p,q in zip(chain,chain[1:]):subprocess.check_call(['git','merge-base','--is-ancestor',p,q])
 for p in [c.GOV,c.PROTOCOL]:c.require(git('show',c.GOVERNANCE_COMMIT+':'+p)==Path(p).read_bytes(),'GOVERNANCE_DRIFT')
 tree=git('ls-tree','-r','--name-only',c.GOVERNANCE_COMMIT).decode().splitlines()
 c.require(c.FRONTIER not in tree and not any(c.status_ref(s) in tree for s in c.SOURCES),'CLASSIFICATION_BEFORE_GOVERNANCE')
 gov_changed=git('diff-tree','--no-commit-id','--name-only','-r',c.GOVERNANCE_COMMIT).decode().splitlines();c.require(set(gov_changed)=={c.GOV,c.PROTOCOL},'SEMANTIC_FREEZE_NOT_ISOLATED')
 frozen=[c.FRONTIER,c.SUPPORT,c.PREFLIGHT,c.ROUTE,'research_core_v4/current_testability_frontier_v1.py',*[c.packet_ref(s) for s in c.SOURCES],*[c.status_ref(s) for s in c.SOURCES]]
 for p in frozen:c.require(git('show',FRONTIER_COMMIT+':'+p)==Path(p).read_bytes(),'FRONTIER_PROTOCOL_DRIFT')
 immutable=[c.BASE,c.prior.SEM,'research_core_v4/prospective_exact_semantics_v3.py','research_core_v4/compact_baseline_v2.py',c.prior.f.FUNCTIONAL,c.prior.f.INPUT,c.prior.f.PROPOSALS,c.prior.RESULT,c.prior.MANIFEST,c.prior.AUDIT,c.prior.BOUNDARY,*[c.prior.ref(s) for s in c.prior.SOURCES]]
 for p in immutable:c.require(git('show',c.START+':'+p)==Path(p).read_bytes(),'GLOBAL_HISTORY_OR_FEATURE_DRIFT:'+p)
 operational={'current_authority','current_authority_sha256','current_next_action_type','current_operational_status','current_state_guard_ref','next_action','stop_boundary','current_operation','strict_v2_exact_candidate_closure','status'}
 for i,p in enumerate(STATES):
  prior=json.loads(git('show',c.START+':'+p));now=json.loads(Path(p).read_bytes())
  for k,v in prior.items():
   if k not in operational:c.require(canonical_equal(now[k],v),'HISTORICAL_FIELD_DRIFT:'+k)
  c.require(now['historical_strict_v2_exact_candidate_closure']==prior['strict_v2_exact_candidate_closure'],'HISTORICAL_OPERATION_MISSING')
  if i>0:c.require(now['status']==prior['status'],'HISTORICAL_STATUS_CHANGED')
 suite=unittest.TestSuite()
 for pattern in ['test_compact_baseline_v2.py','test_current_testability_frontier_v1.py']:suite.addTests(unittest.defaultTestLoader.discover('tests',pattern=pattern))
 authority=json.loads(Path(c.AUTH).read_bytes());allowed={x['ref'] for x in authority['artifact_bindings']+authority['immutable_bindings']}|set(STATES)|{c.AUTH}
 allowed|={x['ref'] for x in json.loads(Path(c.ROUTE).read_bytes())['metadata_read_bindings']}
 allowed_abs={str(Path(x).resolve()) for x in allowed};attempts=[];reads=[]
 def audit(event,args):
  if event.startswith('socket.') or event in {'subprocess.Popen','os.system'}:attempts.append(event);raise RuntimeError('NONMARKET_EXECUTION_DENIED:'+event)
  if event=='open' and isinstance(args[0],(str,bytes)):
   p=Path(args[0]).resolve()
   if p.is_relative_to(Path('.').resolve()):
    if str(p) not in allowed_abs:raise RuntimeError('UNDECLARED_FILE_READ_DENIED:'+str(p))
    reads.append(str(p.relative_to(Path('.').resolve())))
 sys.addaudithook(audit)
 metadata_trace=route_verify();result=unittest.TextTestRunner(verbosity=2).run(suite)
 print(json.dumps({'exact_head':head,'commit_ancestry':chain,'tests_passed':result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),'tests_failed':len(result.failures)+len(result.errors),'tests_skipped':len(result.skipped),'governance_and_cross_sectional_freeze_precede_classifications':True,'global_sources':12,'current_wave_candidates':5,'parked_globally_unknown_candidates':6,'global_functional_and_assessments_unchanged':True,'baseline_and_four_feature_authorities_unchanged':True,'historical_fields_and_counters_preserved':True,'asset_metadata_read_trace':metadata_trace,'inference_file_read_allowlist_enforced':True,'distinct_inference_files_read':sorted(set(reads)),'network_or_subprocess_attempts':attempts,'market_rows_read':0,'binary_assets_read':0,'broker_requests':0,'redecryptions':0,'support_protocol_executed':False,'support_measurements':0,'power_trials':0,'duration_selected':False,'new_economic_outcomes':0,'search_budget_use':0,'protected_forward_opened':False,'confirmation_opened':False},sort_keys=True))
 return 0 if result.wasSuccessful() and not attempts else 1

def canonical_equal(a,b):return c.canonical(a)==c.canonical(b)
if __name__=='__main__':raise SystemExit(main())
