"""Exact-head, offline validation only; no workflow broker credentials."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from research_core_v4 import compact_semantic_closure_v2 as c

def git(*args):return subprocess.check_output(['git',*args])
def main():
 head=git('rev-parse','HEAD').decode().strip()
 # Durable ancestry rather than an in-memory order assertion.
 protocol_commit='0611ac07680898a5cbb922fc112c800e1c93293d'
 subprocess.check_call(['git','merge-base','--is-ancestor',c.FREEZE_COMMIT,protocol_commit])
 subprocess.check_call(['git','merge-base','--is-ancestor',protocol_commit,head])
 c.require(hashlib.sha256(git('show',c.FREEZE_COMMIT+':'+c.BASE)).hexdigest()==c.BASE_HASH,'ANCESTRY_BASELINE_DRIFT')
 c.require(git('show',protocol_commit+':'+c.PROTOCOL)==Path(c.PROTOCOL).read_bytes(),'ANCESTRY_PROTOCOL_DRIFT')
 tree=git('ls-tree','-r','--name-only',protocol_commit).decode().splitlines()
 c.require(not any(c.ref(s) in tree or c.packet_ref(s) in tree for s in c.SOURCES),'OUTPUT_PRECEDED_PROTOCOL')
 before={p:Path(p).read_bytes() for p in [c.f.INPUT,c.f.PROPOSALS,c.f.FUNCTIONAL,c.BASE]}
 suite=unittest.TestSuite()
 for pattern in ['test_compact_baseline_v2.py','test_compact_semantic_closure_v2.py']:suite.addTests(unittest.defaultTestLoader.discover('tests',pattern=pattern))
 network=[]
 def audit(event,args):
  if event.startswith('socket.') or event in {'subprocess.Popen','os.system'}:
   network.append(event);raise RuntimeError('OFFLINE_EXECUTION_DENIED:'+event)
 sys.addaudithook(audit)
 result=unittest.TextTestRunner(verbosity=2).run(suite)
 c.require(all(Path(p).read_bytes()==v for p,v in before.items()),'INPUT_MUTATION')
 print(json.dumps({'exact_head':head,'tests_passed':result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),'tests_failed':len(result.failures)+len(result.errors),'tests_skipped':len(result.skipped),'baseline_freeze_precedes_protocol_and_output':True,'network_attempts':network,'market_rows':0,'power_trials':0,'duration_selected':False},sort_keys=True))
 return 0 if result.wasSuccessful() and not network else 1
if __name__=='__main__':raise SystemExit(main())
