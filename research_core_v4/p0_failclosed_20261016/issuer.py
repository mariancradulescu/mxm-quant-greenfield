"""Inactive issuer boundary. No I/O, credential loader, signer or token client.

This source cannot become operational through config changes. A separately
authorized, reviewed implementation must replace the unconditional deny gates.
"""
import json
from pathlib import Path

CONFIG = Path(__file__).with_name('issuer.disabled.json')


class IssuerDisabled(RuntimeError):
    pass


def validate_disabled(config):
    expected = json.loads(CONFIG.read_text())
    if (expected.get('mode') != 'DISABLED_NO_GO' or
        any(expected.get(k) is not False for k in ('bootstrap_allowed', 'token_issuance_allowed', 'real_write_allowed')) or
        any(expected.get(k) is not None for k in ('auditor_principal', 'auditor_trust_root', 'issuer_principal', 'credential_binding', 'environment_binding'))):
        raise IssuerDisabled('DISABLED_CONFIGURATION_REQUIRED')
    if config != expected:
        raise IssuerDisabled('CONFIG_DRIFT')
    return {'state': 'DISABLED_NO_GO', 'authority_ref': expected['authority_ref'],
            'deny_ruleset_id': expected['deny_ruleset_id'], 'tokens_issued': 0,
            'bootstrap_allowed': False, 'real_write_allowed': False}


def issue_token(*args, **kwargs):
    raise IssuerDisabled('TOKEN_ISSUANCE_NOT_IMPLEMENTED_OR_AUTHORIZED')


def bootstrap(*args, **kwargs):
    raise IssuerDisabled('REAL_BOOTSTRAP_NOT_IMPLEMENTED_OR_AUTHORIZED')


def accept_checkpoint(*args, **kwargs):
    raise IssuerDisabled('REAL_CHECKPOINT_NOT_IMPLEMENTED_OR_AUTHORIZED')
