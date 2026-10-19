import unittest
from unittest.mock import patch
from .runtime import source_admission
RULE={'id':25222248,'enforcement':'active','conditions':{'ref_name':{'include':['refs/heads/mxm-o04-*'],'exclude':[]}},'rules':[{'type':x} for x in ('deletion','non_fast_forward','required_linear_history')],'bypass_actors':[],'updated_at':'2026-10-16T08:41:41.359+02:00'}
class Admission(unittest.TestCase):
    def test_exact_content_and_existing_protection(self):
        source_admission('a'*40,'a'*40,'a'*40,RULE)
    def test_branch_move_does_not_replace_pinned_code(self):
        with self.assertRaisesRegex(ValueError,'IMMUTABLE_SOURCE_PIN'):source_admission('a'*40,'a'*40,'b'*40,RULE)
    def test_checkout_mismatch_blocked(self):
        with self.assertRaisesRegex(ValueError,'IMMUTABLE_SOURCE_PIN'):source_admission('b'*40,'a'*40,'a'*40,RULE)
    def test_changed_independent_protection_stops(self):
        bad={**RULE,'updated_at':'2026-10-17T00:00:00Z'}
        with self.assertRaisesRegex(ValueError,'APPEND_ONLY_FENCE'):source_admission('a'*40,'a'*40,'a'*40,bad)
    def test_visible_bypass_stops(self):
        bad={**RULE,'bypass_actors':[{'actor_id':1}]}
        with self.assertRaisesRegex(ValueError,'APPEND_ONLY_FENCE'):source_admission('a'*40,'a'*40,'a'*40,bad)
if __name__=='__main__':unittest.main()
