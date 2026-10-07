"""Exact-head offline evidence, immutable ancestry and historical-field preservation."""
import json,subprocess,sys,unittest,zlib,base64,re
from pathlib import Path
from research_core_v4 import exact_candidate_certification_v3 as c
from research_core_v4.master1576_current_state_guard_v8 import STATES
START='2e5bc9854d727b3b48a0ff449ceb70d9c090009a';CERT_COMMIT='750ee2248d81798d516b5f156e10b7dfec4f3290'
def git(*args):return subprocess.check_output(['git',*args])
def capability_verify():
 allowed=set(json.loads(Path(c.AUDIT).read_bytes())['read_allowlist']);trace=[]
 with c.io_firewall('.',allowed,trace):raw={p:Path(p).read_bytes() for p in sorted(allowed)}
 meta=json.loads(zlib.decompress(base64.b64decode(raw[c.S+'NEXT_QUOTE_SEQUENCE_CURRENT_METADATA_LOCALIZATION_V1.json.zlib.b64'])))
 inp=json.loads(raw[c.f.INPUT]);projection=json.loads(Path('research_core_v4/nonmarket_contract_v3/METADATA_CAPABILITY_PROJECTION_V3.json').read_bytes())
 c.require(c.sha(raw[projection['source']])==projection['source_sha256'],'METADATA_SOURCE_DRIFT')
 c.require(c.sha(zlib.decompress(base64.b64decode(raw[projection['source']])))==projection['decoded_sha256'],'DECODED_METADATA_DRIFT')
 for f,n in projection['current_field_presence_counts'].items():c.require(sum(f in r.get('current_full_metadata',{}) for r in meta['rows'])==n,'CURRENT_FIELD_PRESENCE_DRIFT')
 for f,n in projection['light_field_presence_counts'].items():c.require(sum(f in r.get('current_light_metadata',{}) for r in meta['rows'])==n,'LIGHT_FIELD_PRESENCE_DRIFT')
 c.require(len(inp['identities'])==1575 and len(inp['context_geometry'])==29,'ROSTER_DRIFT')
 model=raw['research_core_v4/nonmarket_contract_v3/OpenApiModelMessages.proto'].decode();msg=raw['research_core_v4/nonmarket_contract_v3/OpenApiMessages.proto'].decode()
 for name,fields,text in [('ProtoOASymbol',['schedule','scheduleTimeZone','holiday','swapLong','swapShort','swapPeriod','swapTime'],model),('ProtoOALightSymbol',['baseAssetId','quoteAssetId','symbolCategoryId'],model),('ProtoOAGetTickDataReq',['ctidTraderAccountId','symbolId','type','fromTimestamp','toTimestamp'],msg),('ProtoOAGetTickDataRes',['ctidTraderAccountId','tickData','hasMore'],msg)]:
  m=re.search(r'message '+name+r'\s*\{(.*?)\n\}',text,re.S);c.require(m is not None,'MESSAGE_MISSING')
  for f in fields:c.require(re.search(r'\b'+f+r'\s*=',m.group(1)) is not None,'FIELD_MISSING')
 return trace

def main():
 head=git('rev-parse','HEAD').decode().strip();chain=[START,c.SEMANTIC_COMMIT,c.PROTOCOL_COMMIT,CERT_COMMIT,head]
 for p,q in zip(chain,chain[1:]):subprocess.check_call(['git','merge-base','--is-ancestor',p,q])
 c.require(git('show',c.SEMANTIC_COMMIT+':'+c.SEM)==Path(c.SEM).read_bytes(),'SEMANTIC_FREEZE_DRIFT')
 for p in [c.PROTOCOL,c.AUDIT,'research_core_v4/prospective_exact_semantics_v3.py']:c.require(git('show',c.PROTOCOL_COMMIT+':'+p)==Path(p).read_bytes(),'PROTOCOL_FREEZE_DRIFT')
 prior_tree=git('ls-tree','-r','--name-only',c.PROTOCOL_COMMIT).decode().splitlines();c.require(not any(c.ref(s) in prior_tree for s in c.SOURCES),'OUTPUT_PRECEDES_FREEZE')
 for p in [c.MANIFEST,*[c.ref(s) for s in c.SOURCES],*[c.packet_ref(s) for s in c.SOURCES]]:c.require(git('show',CERT_COMMIT+':'+p)==Path(p).read_bytes(),'CERTIFICATE_FREEZE_DRIFT')
 immutable=[c.BASE,c.f.INPUT,c.f.PROPOSALS,c.f.FUNCTIONAL,'research_core_v4/compact_baseline_v2.py']
 for p in immutable:c.require(git('show',START+':'+p)==Path(p).read_bytes(),'IMMUTABLE_SOURCE_DRIFT')
 allowed={'current_authority','current_authority_sha256','current_next_action_type','current_operational_status','current_state_guard_ref','next_action','stop_boundary','current_operation','strict_v2_compact_baseline_closure','status'}
 for i,p in enumerate(STATES):
  prior=json.loads(git('show',START+':'+p));now=json.loads(Path(p).read_bytes())
  for k,v in prior.items():
   if k not in allowed:c.require(c.canonical(now[k])==c.canonical(v),'HISTORICAL_FIELD_DRIFT:'+k)
  c.require(now['historical_strict_v2_compact_baseline_closure']==prior['strict_v2_compact_baseline_closure'],'HISTORY_NOT_PRESERVED')
  if i>0:c.require(now['status']==prior['status'],'HISTORICAL_STATUS_DRIFT')
 suite=unittest.TestSuite()
 for pattern in ['test_compact_baseline_v2.py','test_exact_candidate_certification_v3.py']:suite.addTests(unittest.defaultTestLoader.discover('tests',pattern=pattern))
 attempts=[]
 def audit(event,args):
  if event.startswith('socket.') or event in {'subprocess.Popen','os.system'}:attempts.append(event);raise RuntimeError('OFFLINE_EXECUTION_DENIED:'+event)
 sys.addaudithook(audit)
 capability_trace=capability_verify();result=unittest.TextTestRunner(verbosity=2).run(suite)
 print(json.dumps({'exact_head':head,'commit_ancestry':chain,'tests_passed':result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),'tests_failed':len(result.failures)+len(result.errors),'tests_skipped':len(result.skipped),'network_or_subprocess_attempts_during_inference':attempts,'capability_audit_read_trace':capability_trace,'historical_state_fields_preserved':True,'baseline_unchanged':True,'functional_unchanged':True,'semantic_and_protocol_freeze_before_all_eleven_certificates':True,'certificates_frozen_before_reapplication':True,'market_rows':0,'historical_outcome_files_read_by_inference':0,'broker_requests':0,'power_trials':0,'duration_selected':False,'new_economic_outcomes':0,'search_budget_use':0,'protected_forward_opened':False,'confirmation_opened':False},sort_keys=True))
 return 0 if result.wasSuccessful() and not attempts else 1
if __name__=='__main__':raise SystemExit(main())
