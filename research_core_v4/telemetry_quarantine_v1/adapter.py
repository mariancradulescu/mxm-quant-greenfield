"""Separate live adapter; inert without exact ARM, audit, bindings and custody."""
from __future__ import annotations
import json
import struct
import subprocess
import time
from pathlib import Path
from .core import ARM_PATH, ALLOWED, Denied, arm_gate, canonical, require, sha

AUTH_PATH='research_core_v4/state/TELEMETRY_QUARANTINE_INDEPENDENT_EXECUTION_AUTHORIZATION_V1.json'
PARTITION_PATH='research_core_v4/telemetry_quarantine_v1/PARTITION_V1.json'
FREEZE_PATH='research_core_v4/telemetry_quarantine_v1/PREARM_FREEZE_V1.json'
STOP_PATH='research_core_v4/state/STRICT_PREOUTCOME_OPERATIONAL_V2_EXTENDED_28_WEEK_FAILURE_PROJECT_GOVERNANCE_STOP_V1.json'

def read_json(root,p):return json.loads((Path(root)/p).read_bytes())
def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()

def preflight(root, now_ns):
    root=Path(root)
    require((root/ARM_PATH).is_file(),'SEPARATE_ARM_REQUIRED')
    require((root/AUTH_PATH).is_file(),'INDEPENDENT_AUTH_REQUIRED')
    p=read_json(root,PARTITION_PATH); freeze=read_json(root,FREEZE_PATH)
    for rel,h in freeze['bindings'].items():require(sha((root/rel).read_bytes())==h,'IMMUTABLE_BINDING:'+rel)
    arm=read_json(root,ARM_PATH);auth=read_json(root,AUTH_PATH)
    head=git(root,'rev-parse','HEAD');parent=git(root,'rev-parse','HEAD^')
    changed=git(root,'diff-tree','--no-commit-id','--name-only','-r','HEAD').splitlines()
    require(not git(root,'status','--porcelain'),'DIRTY_WORKTREE')
    # Every change after the audited historical head is enumerated; unknown drift denies.
    drift=git(root,'diff','--name-only',p['base_head'],parent).splitlines()
    require(set(drift)<=set(freeze['allowed_prearm_added_paths'])|{AUTH_PATH},'UNREVIEWED_REPOSITORY_DRIFT')
    arm_gate(arm,auth,p,(root/STOP_PATH).read_bytes(),head,parent,changed,now_ns)
    return arm,auth,p

class OfflineFixtureAdapter:
    """Fixture-only framing harness. Real TLS integration is intentionally unpublished."""
    def __init__(self, transport, capture, decoder, witness_supplier,
                 utc_clock=time.time_ns, mono_clock=time.monotonic_ns):
        require(getattr(transport,'no_network_fixture',False) is True,'OFFLINE_FIXTURE_TRANSPORT_REQUIRED')
        self.transport=transport;self.capture=capture;self.decoder=decoder
        self.witness_supplier=witness_supplier;self.utc=utc_clock;self.mono=mono_clock
        self.authenticated_view=False
    def mark_account_scope(self,actual_permission_scope,actual_fingerprint,expected_fingerprint):
        require(actual_permission_scope==0,'SCOPE_VIEW_ONLY')
        require(actual_fingerprint==expected_fingerprint,'ACCOUNT_FINGERPRINT')
        self.authenticated_view=True
    def receive(self,deadline):
        # Pair UTC immediately after receiving the body, before decoding/encrypting.
        try:
            header=self.transport._recv_exact(4,deadline=deadline)
            n=struct.unpack('!I',header)[0]
            require(0<n<=self.capture.p['limits']['max_frame_bytes'],'FRAME_BUDGET')
            raw=self.transport._recv_exact(n,deadline=deadline)
            before=self.mono(); wall=self.utc(); after=self.mono()
            pair=self.capture.clock.pair(before,wall,after,self.witness_supplier())
            event=self.decoder(raw)
            return self.capture.ingest(raw,event,pair)
        except Exception:
            self.capture.mark_connection_loss();raise

def prepare_live(root,now_ns,custody_attestation,transport_factory=None):
    """No default live entrypoint. Verify all prerequisites before constructing transport."""
    arm,auth,p=preflight(root,now_ns)
    require(custody_attestation=={'scope_hash':arm['scope_hash'],'pilot_id':arm['pilot_id'],
            'key_sha256':arm['key_sha256'],'independent_key_owner':True,
            'private_key_unavailable_to_director':True,'storage_isolated':True},'CUSTODY_ATTESTATION')
    require(auth.get('clock_witness_contract_verified') is True,'CLOCK_WITNESS_NOT_CERTIFIED')
    raise Denied('PREARM_NOT_READY_ENCRYPTION_PREFLIGHT_FAILED')
