"""Independent live public checkpoint20 preflight. No keys, writes or broker requests.

This checks the actual GitHub evidence and authority; it expressly does NOT
pretend that the R3 source has been sealed or that R3 private cold decrypt ran.
"""
import json
from pathlib import Path
from .common import need,digest
from .protocol import verify_checkpoint20_public
from .runtime import file_at
from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
from research_core_v4.remediation_p0_p4_20261015.safety import strict_json

ROOT=Path(__file__).resolve().parent
EVIDENCE='09703adad6433f395a0506fa640f59bf3dba80b5'
SOURCE='eab050084982916ad0c67798b38b947bac66b2b2'
OWNER='a830c132521bd4348454653f713e04f6107484fe'
ACTIVE='07d1ddbe0b83753bbf189770af1911623fef8d6f'

def evidence_origin(route,head,limit=256):
    """The original checkpoint is conserved inside a linear append-only history.

    A legitimate claim/recovery/segment advances HEAD. It cannot invalidate the
    fixed checkpoint20 authority, and a detached old blob alone is insufficient.
    Walk small commit metadata instead of downloading ciphertext diffs.
    """
    import re
    seen=set();oid=head
    for _ in range(limit):
        need(type(oid) is str and re.fullmatch('[a-f0-9]{40}',oid) and oid not in seen,
             'R3_PREFLIGHT_EVIDENCE_LINEAGE_IDENTITY')
        if oid==EVIDENCE:return {'head':head,'origin':EVIDENCE,'successor_commits':len(seen)}
        seen.add(oid);commit=route.json('git/commits/'+oid)
        need(commit.get('sha')==oid and len(commit.get('parents',[]))==1,
             'R3_PREFLIGHT_EVIDENCE_LINEAR_HISTORY')
        oid=commit['parents'][0]['sha']
    need(False,'R3_PREFLIGHT_EVIDENCE_LINEAGE_BOUND')

def main():
    route=GetOnly()
    for branch,sha in [('mxm-o04-integrated-laboratory-evidence',EVIDENCE),
                       ('mxm-o04-successor-code-integrated-p0-r2',SOURCE),
                       ('mxm-o04-accepted-owner-1807-v1',OWNER),
                       ('mxm-o04-active-v1',ACTIVE)]:
        actual=route.json('branches/'+branch)
        need((branch=='mxm-o04-integrated-laboratory-evidence' or actual['commit']['sha']==sha) and actual['protected'] is True,
             'R3_PREFLIGHT_PROTECTED_ANCHOR_'+branch.upper().replace('-','_'))
        if branch=='mxm-o04-integrated-laboratory-evidence':lineage=evidence_origin(route,actual['commit']['sha'])
    state=strict_json(file_at(route,'typed-successor/program-state.json',EVIDENCE))
    fixture=strict_json((ROOT/'fixtures/sealed_checkpoint20_public.json').read_bytes())
    need(state==fixture,'R3_PREFLIGHT_PUBLIC_CHECKPOINT_CHANGED')
    a={'schema':'mxm.integrated-typed-predecessor.v3',
       'evidence_oid':EVIDENCE,'source_sha':SOURCE,'sequence':20,
       'ciphertext_sha256':state['ciphertext_sha256'],
       'private_sha256':'01227d7a7715a89bc1bfcf6fac183fbaec3b941f8c61281fb3c0e4f01f232fa6',
       'public_state_sha256':digest(state)}
    verify_checkpoint20_public(state,a,EVIDENCE)
    main_protected=route.json('branches/main')['protected'] is True
    execution_protected=route.json('branches/mxm-remediation-p0-p4-20261015-v1')['protected'] is True
    print(json.dumps({'schema':'mxm.r3.public-preflight.v2',
                      'checkpoint_sequence':20,'checkpoint_evidence_oid':EVIDENCE,
                      'exact_public_state_sha256':digest(state),
                      'owner_anchor_unchanged':True,
                      'active_authority_unchanged':True,
                      'r2_source_protected':True,
                      'evidence_lineage':lineage,
                      'private_migration_and_runtime_acceptance_evaluated':False,
                      'main_protected':main_protected,
                      'execution_protected':execution_protected,
                      'end_to_end_operational_certificate_issued':False,
                      'orders':0,'new_economic_outcomes':0},sort_keys=True))
if __name__=='__main__':
    main()
