import json,os
from datetime import datetime,timezone
from research_core_v4.aidr_cost_coverage_v1 import frontier_runtime_v1 as rt
e=rt.e
P='research_core_v4/synchronized_breadth_v1/'
def gate():
    head=os.environ['GITHUB_SHA'];e.w.v2.runtime(head)
    auth=json.loads((e.a.ROOT/(P+'EXECUTION_V1.json')).read_text())
    e.w.old.need(auth['authority']=='EXPLICIT_OWNER_COST_FIRST_DISTINCT_BREADTH_20261010' and not auth['orders'] and not auth['protected_forward'],'BREADTH_SCOPE')
    e.w.old.need(os.environ.get('GITHUB_EVENT_NAME')=='push' and os.environ['GITHUB_WORKFLOW_REF']==e.w.old.REPO+'/.github/workflows/mxm-synchronized-breadth-v1.yml@refs/heads/'+e.w.old.BRANCH,'BREADTH_WORKFLOW')
    e.w.old.need(datetime.now(timezone.utc).isoformat()<auth['expires_utc'],'BREADTH_EXPIRED');e.a.ancestor(auth['base_head'],head)
    for p,h in auth['bindings'].items():e.w.old.need(e.w.old.filehash(p)==h,'BREADTH_SOURCE_DRIFT')
    original=json.loads((e.a.ROOT/(e.P+'EXACT_COVERAGE_PREARM_V1.json')).read_text())
    for p,h in original['bindings'].items():e.w.old.need(e.w.old.filehash(p)==h,'ORIGINAL_SOURCE_DRIFT')
    e.w.old.verify_science();claim='mxm-owner-breadth-'+auth['invocation_id']
    e.w.old.need(not e.w.v2.existing_ref(claim),'BREADTH_CONSUMED');e.w.old.api('git/refs',{'ref':'refs/tags/'+claim,'sha':head})
    return head,auth
