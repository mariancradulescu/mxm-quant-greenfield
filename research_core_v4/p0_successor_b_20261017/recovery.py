"""Real OWNER1807 restoration into a read-only successor input.

Uses the existing encrypted asset decoder and existing key, never legacy main().
No market calls, outcome recomputation, release mutation or UNKNOWN promotion.
"""
import dataclasses
import pathlib
import tempfile
import os
from research_core_v4.p0_supersession_20261016.authority import OWNER_ROOT, need, digest, canonical
from research_core_v4.remediation_p0_p4_20261015 import owner
from research_core_v4.remediation_p0_p4_20261015.resolution import unique_metadata
from research_core_v4.remediation_p0_p4_20261015.safety import strict_json, clean_tree
from research_core_v4.asymmetric_recovery_v4_gate import _private_key_from_secret

@dataclasses.dataclass(frozen=True)
class RestoredCheckpoint:
    generation: int
    journal_sha256: str
    journal: dict = dataclasses.field(repr=False)
    execution_allowed: bool = False
    research_allowed: bool = False

def parse_verified(journal, expected_digest):
    need(expected_digest==OWNER_ROOT[3] and digest(canonical(journal))==expected_digest,
         'B_REAL_JOURNAL_HASH')
    need(type(journal) is dict and journal.get('generation')==1807 and
         not journal.get('pending_requests'), 'B_REAL_JOURNAL_NOT_CLEAN')
    need(type(journal.get('autonomy')) is dict and
         type(journal['autonomy'].get('sequence')) is int, 'B_REAL_RUNTIME_STATE')
    # Inventory validates every direct source reference; it does not claim that
    # source assets are available or semantically admitted for future research.
    unique_metadata(journal)
    return RestoredCheckpoint(1807,expected_digest,journal)

def recover():
    root=pathlib.Path(__file__).resolve().parents[2];clean_tree(root)
    need(os.environ.get('GITHUB_REF_NAME')=='mxm-remediation-p0-p4-20261015-v1' and
         os.environ.get('GITHUB_RUN_ATTEMPT')=='1','B_RECOVERY_WORKLOAD')
    before=owner.get('releases/412686323');body=strict_json(before['body'])
    need(body['generation']==1807 and body['state']=='STOP_FAIL_CLOSED' and
         body['pending_request_count']==0,'B_OWNER_STOP_ROOT')
    m=body['current_journal']
    need(m['id']==642889915 and m['canonical_sha256']==OWNER_ROOT[3] and
         m['ciphertext_sha256']==owner.CIPHER and m['gzip_sha256']==owner.PACKED,
         'B_REAL_ASSET_PIN')
    with tempfile.TemporaryDirectory(dir=os.environ.get('RUNNER_TEMP')) as d:
        key,fp=_private_key_from_secret(pathlib.Path(d));need(fp==owner.FP,'B_OWNER_KEY')
        restored=parse_verified(owner.read_asset(m,key,pathlib.Path(d)),m['canonical_sha256'])
        sources=unique_metadata(restored.journal)
        # Only digests/counts cross the process boundary. Private tables and key
        # never enter logs, artifacts, Git, command arguments or public state.
        receipt={'schema':'mxm.successor-real-restore.v1','generation':restored.generation,
                 'journal_sha256':restored.journal_sha256,
                 'runtime_sequence':restored.journal['autonomy']['sequence'],
                 'direct_source_count':len(sources),'source_inventory_sha256':digest(canonical(sources)),
                 'execution_allowed':False,'research_allowed':False,'broker_requests':0,
                 'source_assets_read':0,'orders':0,'historical_restart':False,
                 'semantic_admission':'UNCHANGED_UNKNOWN_REMAINS_QUARANTINED',
                 'source_head':os.environ['GITHUB_SHA'],'run_id':os.environ['GITHUB_RUN_ID']}
    need(owner.get('releases/412686323')['body']==before['body'],'B_ORIGINAL_CHANGED')
    need(owner.get('git/ref/heads/mxm-o04-accepted-owner-1807-v1')['object']['sha']==OWNER_ROOT[1],
         'B_OWNER_REF_CHANGED')
    out=root/'verification/successor-b';out.mkdir(parents=True,exist_ok=True)
    (out/'real-restore.json').write_bytes(canonical(receipt))
    print(canonical(receipt).decode())

if __name__=='__main__':
    # Reuse the existing process-wide GET-only route, including the legacy
    # decoder's downloads. No historical scanner or economic engine is run.
    import urllib.request
    from research_core_v4.remediation_p0_p4_20261015.rest29_v3 import GetOnly
    route=GetOnly();old_get=owner.get;old_open=urllib.request.urlopen
    owner.get=route.json;urllib.request.urlopen=route.open
    try:recover()
    except Exception:
        print('{"state":"B_REAL_RESTORE_BLOCKED","private_details_omitted":true}')
        raise SystemExit(1) from None
    finally:
        owner.get=old_get;urllib.request.urlopen=old_open
