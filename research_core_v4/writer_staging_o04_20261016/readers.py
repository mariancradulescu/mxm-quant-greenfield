"""Opt-in staging adapters. Never import/execute historical campaign readers."""
from .protocol import owner_reader,staging_reader
ENTRYPOINTS={
 'owner_checkpoint_readback':'research_core_v4/remediation_p0_p4_20261015/owner.py:main',
 'cold_owner_readback':'research_core_v4/remediation_p0_p4_20261015/owner.py:child',
 'frontier_restore':'research_core_v4/full_native_frontier_20261014_v1/runner_v1.py:restore',
 'frontier_asset_restore':'research_core_v4/full_native_frontier_20261014_v1/runner_v1.py:FrontierStore.restore',
}
def dry_run(entrypoint,selected_ref,oid,state,issuer,source,gate_ref):
    if entrypoint not in ENTRYPOINTS:return {'OWNER':'NOT_AUTHORIZED','STAGING':'NOT_AUTHORIZED','science':'UNKNOWN'}
    stage=staging_reader(selected_ref,oid,state,issuer,source) if selected_ref==gate_ref else 'NOT_AUTHORIZED'
    return {'entrypoint':ENTRYPOINTS[entrypoint],'OWNER':owner_reader(selected_ref,{'oid':oid}),
            'STAGING':stage,'science':'UNKNOWN','dispatches':0,'broker_requests':0}
