"""Owner-authorized numerical cost frontier on existing authenticated data only."""
import os,json,pathlib,tempfile,subprocess
from datetime import datetime,timezone
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
from research_core_v4.owner_recovery_v1.runtime_v1 import load_asset
from research_core_v4.executable_coverage_diagnostic_v1.runner_v1 import relay
from .economics_v1 import evaluate
e=rt.e;P='research_core_v4/complete_strategy_frontier_v1/';PHASE='GATE'
def need(x,c):e.w.old.need(bool(x),c)
def main():
 global PHASE
 os.umask(0o077);head=os.environ['GITHUB_SHA'];auth=json.loads((e.a.ROOT/(P+'STAGE_A_EXECUTION_V1.json')).read_text());e.w.v2.runtime(head);need(auth['authority']=='EXPLICIT_OWNER_COMPLETE_STRATEGY_FRONTIER_20261012','OWNER_SCOPE');need(not any(auth[n] for n in ('orders','protected_forward','broker_requests','closed_kernel_replay','cloud_changes')),'STAGE_A_SCOPE');need(os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-complete-strategy-stage-a-v1.yml@refs/heads/'+e.w.old.BRANCH,'WORKFLOW');need(datetime.now(timezone.utc).isoformat()<auth['expires_utc'],'EXPIRED')
 for path,sha in auth['bindings'].items():need(e.w.old.filehash(path)==sha,'SOURCE_BINDING')
 e.a.ancestor(auth['base_head'],head);e.a.ancestor(auth['design_commit'],head);old=subprocess.check_output(['git','ls-tree','-r',auth['base_head']],cwd=e.a.ROOT,text=True).splitlines();new=set(subprocess.check_output(['git','ls-tree','-r',head],cwd=e.a.ROOT,text=True).splitlines());need(all(x in new for x in old),'OLD_FILES_PRESERVED');e.w.old.verify_science();need(not e.w.v2.existing_ref(auth['one_use_ref']),'ONE_USE');e.w.old.api('git/refs',{'ref':'refs/tags/'+auth['one_use_ref'],'sha':head})
 with tempfile.TemporaryDirectory(prefix='mxm-strategy-cost-',dir=os.environ['RUNNER_TEMP']) as td:
  tmp=pathlib.Path(td);key,fp=e.w.old._private_key_from_secret(tmp);need(fp==e.w.old.FP,'EXISTING_OWNER_KEY');PHASE='AUTHENTIC_EXISTING_SOURCE';full,proof=load_asset(key,fp,tmp,auth['source']);need(full['summary']['source_head']==auth['numeric_source_head'],'SOURCE_HEAD');PHASE='NATIVE_COST_HURDLES_NO_NEW_LABELS';result,summary=evaluate(full);summary.update(source_head=head,design_commit=auth['design_commit'],input_provenance=[proof],classification='DEVELOPMENT_ECONOMIC_FEASIBILITY_NOT_NEW_ALPHA',historical_terms='DATED_CURRENT_REFERENCE;HISTORICAL_FUNDING_FEES_FILLS_UNRESOLVED');PHASE='ENCRYPTED_OUTPUT';rt.output(head,auth,tmp,key,'strategyfeasibility',result,summary);relay(head,auth,tmp,summary)
if __name__=='__main__':
 try:main()
 except Exception as exc:rt.fail(exc,PHASE);raise SystemExit(1)
