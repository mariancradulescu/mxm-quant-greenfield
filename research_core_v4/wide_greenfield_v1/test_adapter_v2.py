import unittest
from research_core_v4.wide_greenfield_v1.collect_v2 import native_identity_ok
class IdentityTests(unittest.TestCase):
 def test_casefold_native_identity_matches_accepted_collector(self):
  self.assertTrue(native_identity_ok({'deposit_currency':'EUR','broker_name':'pepperstone eu limited'}))
  self.assertFalse(native_identity_ok({'deposit_currency':'USD','broker_name':'Pepperstone'}))
  self.assertFalse(native_identity_ok({'deposit_currency':'EUR','broker_name':'Other Broker'}))
