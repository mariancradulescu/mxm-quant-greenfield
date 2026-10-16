"""Versioned, filesystem-only bootstrap rehearsal. No production writer exists here.

The accepted O04 transport is reused unchanged. Two synthetic signers model
separate approvals; neither is an OWNER/auditor credential or a GitHub grant.
"""
import base64
import copy
import hashlib
import json
from pathlib import Path
import re
from ..writer_fencing_o04_20261016 import git_fence_lab as lab

STOP = 'a830c132521bd4348454653f713e04f6107484fe'
STAGING = 'c6644174244cd92b8e41b17f241b8f5e545fddd9'
TARGET = 'refs/heads/mxm-o04-active-v1'
ROLES = ('OWNER_SYNTHETIC', 'AUDITOR_SYNTHETIC')
FLAGS = {'OWNER_ACCEPTS_NEW_CHECKPOINTS': False, 'CAMPAIGN_RESTART_ALLOWED': False,
         'PRODUCTION_GO': False, 'RESEARCH_GO': False}
FIELDS = {'schema', 'marker', 'plan_sha256', 'source_SHA', 'root_stop_oid',
          'staging_oid', 'target_ref', 'policy_sha256', 'operation_id', 'epoch',
          'version', 'not_before', 'expires_at', 'scope', 'permissions'}

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def canonical(value):
    return lab.canonical(value)

def closed_flags(value):
    return isinstance(value, dict) and set(value) == set(FLAGS) and all(v is False for v in value.values())

def load_spec():
    return json.loads(Path(__file__).with_name('TRANSITION_SPEC.json').read_bytes())

def validate_spec(spec):
    lab.need(spec['schema'] == 'mxm.p0.writer-transition.preparation.v1' and
             spec['mode'] == 'PREPARATION_ONLY_NO_GO', 'SPEC_MODE')
    lab.need(spec['root_stop_oid'] == STOP and spec['owner_generation'] == 1807 and
             spec['staging_oid'] == STAGING, 'ROOT_BINDING')
    lab.need(spec['future_authority_ref'] == TARGET, 'FIXED_FUTURE_REFERENCE')
    lab.need(closed_flags(spec['invariants']), 'SPEC_REAL_GO_FORBIDDEN')
    lab.need(spec['permissions'] == {'github_job': {'contents': 'read', 'actions': 'read'},
             'App_key': False, 'OWNER_key': False, 'environment': False, 'oidc_token': False},
             'PREPARATION_PRIVILEGES')
    lab.need(spec['synthetic_protocol']['real_backend'] == 'UNCONDITIONALLY_DISABLED',
             'REAL_BACKEND_FORBIDDEN')
    return sha(canonical(spec))

class SyntheticApprovalGate:
    """Trust objects come from the test harness, never from an approval payload.

    This deliberately accepts ONLY the synthetic approval schema and scope.
    A future real gate needs separately installed independent trust roots.
    """
    def __init__(self, spec, source_sha, policy_sha, trusted_signers, clock):
        self.spec = copy.deepcopy(spec)
        self.plan_sha = validate_spec(self.spec)
        lab.need(re.fullmatch('[0-9a-f]{40}', source_sha) is not None, 'SOURCE_SHA')
        lab.need(re.fullmatch('[0-9a-f]{64}', policy_sha) is not None, 'POLICY_DIGEST')
        self.source = source_sha
        self.policy = policy_sha
        self.signers = dict(trusted_signers)
        lab.need(set(self.signers) == set(ROLES), 'TRUST_ROLES')
        lab.need(len({s.fingerprint for s in self.signers.values()}) == 2, 'DISTINCT_TRUST_ROOTS')
        self.clock = clock

    def statement(self, operation='synthetic-bootstrap-1', epoch=1):
        now = self.clock()
        return {'schema': 'mxm.p0.synthetic-transition-approval.v1', 'marker': 'SYNTHETIC_ONLY',
                'plan_sha256': self.plan_sha, 'source_SHA': self.source,
                'root_stop_oid': STOP, 'staging_oid': STAGING, 'target_ref': TARGET,
                'policy_sha256': self.policy, 'operation_id': operation, 'epoch': epoch,
                'version': 1, 'not_before': now, 'expires_at': now + 120,
                'scope': 'SYNTHETIC_BOOTSTRAP_ONLY', 'permissions': FLAGS.copy()}

    def validate(self, statement, approvals, epoch):
        lab.need(isinstance(statement, dict) and set(statement) == FIELDS, 'APPROVAL_FIELDS')
        expected = {'schema': 'mxm.p0.synthetic-transition-approval.v1',
                    'marker': 'SYNTHETIC_ONLY', 'plan_sha256': self.plan_sha,
                    'source_SHA': self.source, 'root_stop_oid': STOP,
                    'staging_oid': STAGING, 'target_ref': TARGET,
                    'policy_sha256': self.policy, 'scope': 'SYNTHETIC_BOOTSTRAP_ONLY',
                    'permissions': FLAGS}
        for field, value in expected.items():
            lab.need(statement[field] == value, 'BINDING_' + field.upper())
        lab.need(closed_flags(statement['permissions']), 'BINDING_PERMISSIONS')
        lab.need(type(epoch) is int and type(statement['epoch']) is int and
                 statement['epoch'] == epoch and epoch > 0, 'EPOCH')
        lab.need(type(statement['version']) is int and statement['version'] == 1, 'VERSION')
        now = self.clock()
        lab.need(type(now) is int and type(statement['not_before']) is int and
                 type(statement['expires_at']) is int and
                 statement['not_before'] <= now < statement['expires_at'] and
                 0 < statement['expires_at'] - statement['not_before'] <= 300, 'APPROVAL_TIME')
        lab.need(isinstance(statement['operation_id'], str) and
                 re.fullmatch('[a-z0-9-]{1,80}', statement['operation_id']) is not None, 'OPERATION')
        lab.need(isinstance(approvals, list) and len(approvals) == 2, 'TWO_APPROVALS')
        seen = set()
        for a in approvals:
            lab.need(isinstance(a, dict) and set(a) == {'role', 'key_sha256', 'signature'}, 'SIGNER_FIELDS')
            role = a['role']
            lab.need(role in ROLES and role not in seen, 'SIGNER_ROLE')
            seen.add(role)
            signer = self.signers[role]
            lab.need(a['key_sha256'] == signer.fingerprint, 'TRUST_ROOT')
            # Role is part of the signed message, preventing cross-role reuse.
            lab.need(signer.verify({'role': role, 'statement': statement}, a['signature']), 'SIGNATURE')
        lab.need(seen == set(ROLES), 'TWO_ROLES')
        return sha(canonical(statement))

def synthetic_approvals(gate, statement):
    return [{'role': role, 'key_sha256': gate.signers[role].fingerprint,
             'signature': base64.b64encode(gate.signers[role].sign(
                 {'role': role, 'statement': statement})).decode()} for role in ROLES]

class LocalBootstrap:
    """Can use only the existing marked local bare Git lab. No live ref argument."""
    def __init__(self, transport, gate):
        lab.need(type(transport) is lab.GitFenceLab, 'FILESYSTEM_LAB_ONLY')
        self.transport = transport
        self.gate = gate

    def initialize(self):
        return self.transport._publish(lab.ZERO, {
            'schema': 'mxm.o04.synthetic.git-fence.v1', 'marker': 'SYNTHETIC_ONLY',
            'phase': 'SYNTHETIC_STOP', 'root_stop_oid': STOP, 'owner_generation': 1807,
            'plan_sha256': self.gate.plan_sha, 'epoch': 1, 'version': 0,
            'operation_id': None, 'pending': None, 'permissions': FLAGS.copy()})

    def read(self):
        oid, state = self.transport.read()
        lab.need(state['marker'] == 'SYNTHETIC_ONLY' and state['root_stop_oid'] == STOP and
                 state['owner_generation'] == 1807, 'SYNTHETIC_ROOT')
        lab.need(closed_flags(state['permissions']) and state['plan_sha256'] == self.gate.plan_sha,
                 'STATE_BINDING')
        return oid, state

    def prepare(self, expected_oid, statement, approvals):
        oid, state = self.read()
        lab.need(oid == expected_oid and state['phase'] == 'SYNTHETIC_STOP', 'PREPARE_STATE')
        digest = self.gate.validate(statement, approvals, state['epoch'])
        state = copy.deepcopy(state)
        state.update(phase='PREPARED_SYNTHETIC', pending={'statement': statement,
                     'approvals': approvals, 'digest': digest, 'expected_stop_oid': oid})
        return self.transport._publish(oid, state)

    def commit(self, expected_oid, lose_ack=False):
        oid, state = self.read()
        lab.need(oid == expected_oid and state['phase'] == 'PREPARED_SYNTHETIC', 'BOOTSTRAP_STATE')
        pending = state['pending']
        digest = self.gate.validate(pending['statement'], pending['approvals'], state['epoch'])
        lab.need(digest == pending['digest'], 'PENDING_DIGEST')
        state = copy.deepcopy(state)
        state.update(phase='SIMULATED_BOOTSTRAP_NO_GO', version=1,
                     operation_id=pending['statement']['operation_id'],
                     approval_digest=digest, pending=None)
        return self.transport._publish(oid, state, lose_ack=lose_ack)

    def resolve(self, operation, digest):
        oid, state = self.read()
        if (state['phase'] == 'SIMULATED_BOOTSTRAP_NO_GO' and state['version'] == 1 and
                state['operation_id'] == operation and state['approval_digest'] == digest):
            return {'decision': 'SIMULATED_COMMIT_FOUND_NO_REPLAY', 'oid': oid}
        return {'decision': 'UNKNOWN_STOP_NO_RETRY', 'oid': oid}

def select_route(ref, workflow_path, historical_paths):
    if workflow_path in historical_paths:
        return 'DENIED_HISTORICAL_ROUTE'
    if ref == 'refs/heads/mxm-o04-accepted-owner-1807-v1':
        return 'OBSERVE_STOP_ONLY'
    if ref == 'refs/heads/mxm-o04-stage-authority-v1':
        return 'OBSERVE_ACCEPTED_STAGING_ONLY'
    # Includes the future active ref, other side refs, releases and legacy routes.
    return 'NOT_AUTHORIZED'

def production_checkpoint(*args, **kwargs):
    # No signed-looking payload, GO boolean, environment or CLI can open this.
    raise lab.Denied('REAL_WRITER_NOT_IMPLEMENTED_NO_GO')
