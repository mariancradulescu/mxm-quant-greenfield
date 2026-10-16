"""Observe this unapproved test run, never approve a deployment."""
import json
import os
from pathlib import Path
from .governance import GitHubReadOnly
from research_core_v4.p0_supersession_20261016.authority import digest,need


def main():
    run_id=int(os.environ['GITHUB_RUN_ID'])
    run,reviews=GitHubReadOnly().review_history(run_id)
    need(run['head_sha']==os.environ['GITHUB_SHA'] and run['run_attempt']==1,'OBSERVED_RUN_BINDING')
    # This workflow has no critical environment, grant or approval action.
    need(reviews==[],'UNEXPECTED_REVIEW_ON_UNGATED_TEST_RUN')
    folder=Path('research_core_v4/p0_owner_governance_20261017')
    paths=list(sorted(folder.glob('*.py')))+[Path('.github/workflows/mxm-p0-owner-governance-20261017.yml')]
    out=Path('verification/p0-owner-governance');out.mkdir(parents=True,exist_ok=True)
    (out/'native-observation.json').write_text(json.dumps({'schema':'mxm.owner-boundary.native-readonly.v1',
        'run_id':run_id,'attempt':1,'source_sha':os.environ['GITHUB_SHA'],
        'calls':[{'method':'GET','path':'actions/runs/'+str(run_id)},
                 {'method':'GET','path':'actions/runs/'+str(run_id)+'/approvals'}],
        'run_actor_id':run['actor']['id'],'run_actor_is_not_approval':True,'review_history':reviews,
        'owner_critical_authorization_observed':False,'approval_mutations':0,'authority_writes':0,
        'source_sha256':{str(p):digest(p.read_bytes()) for p in paths}},indent=2)+'\n')
    print(json.dumps({'native_GETs':2,'review_history':reviews,'owner_authorization':False,'writes':0}))


if __name__=='__main__':main()
