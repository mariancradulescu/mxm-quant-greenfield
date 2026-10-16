"""New narrow tests only; does not import historic or O04.2 runtime modules."""
import copy
import json
import unittest
from .issuer import CONFIG, IssuerDisabled, validate_disabled, issue_token, bootstrap, accept_checkpoint


class DisabledBoundary(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(CONFIG.read_text())

    def test_disabled_config(self):
        self.assertEqual(validate_disabled(self.config)['tokens_issued'], 0)

    def test_token_denied(self):
        with self.assertRaises(IssuerDisabled): issue_token(self.config)

    def test_bootstrap_denied(self):
        with self.assertRaises(IssuerDisabled): bootstrap(self.config)

    def test_checkpoint_denied(self):
        with self.assertRaises(IssuerDisabled): accept_checkpoint({'generation': 1808})

    def test_activation_flags_denied(self):
        for field in ('bootstrap_allowed', 'token_issuance_allowed', 'real_write_allowed', 'mode'):
            c = copy.deepcopy(self.config); c[field] = True
            with self.subTest(field=field), self.assertRaises(IssuerDisabled): validate_disabled(c)

    def test_credential_and_principal_binding_denied(self):
        for field in ('credential_binding', 'environment_binding', 'issuer_principal', 'auditor_principal', 'auditor_trust_root'):
            c = copy.deepcopy(self.config); c[field] = 'SYNTHETIC_NOT_A_CREDENTIAL'
            with self.subTest(field=field), self.assertRaises(IssuerDisabled): validate_disabled(c)

    def test_reference_and_root_drift_denied(self):
        for field in ('authority_ref', 'owner_oid', 'owner_ref', 'owner_generation', 'deny_ruleset_id', 'repository'):
            c = copy.deepcopy(self.config); c[field] = 'SYNTHETIC_DRIFT'
            with self.subTest(field=field), self.assertRaises(IssuerDisabled): validate_disabled(c)

    def test_extra_fields_denied(self):
        with self.assertRaises(IssuerDisabled): validate_disabled({**self.config, 'bypass': True})


if __name__ == '__main__': unittest.main(verbosity=2)
