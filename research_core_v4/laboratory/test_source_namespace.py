"""Regression for native merge-history creation refusal and fence drift."""
import unittest
from . import runtime,test_source_freeze as fixtures
from .test_source_freeze import Route
from .common import LabError

class SourceNamespace(unittest.TestCase):
    def check(self,route):return fixtures.SourceFreeze.check(self,route)

    def test_immutable_source_does_not_require_rewriting_merge_history(self):
        # GitHub rejects creation under the historical linear-only namespace.
        # The operational source instead requires the exact immutable seal.
        self.assertEqual(runtime.SOURCE_BRANCH,'mxm-r3-integrated-source-20261021-r3')
        self.check(Route())

    def test_historical_authority_fence_scope_cannot_change(self):
        for include,exclude in ((['refs/heads/*'],[]),(['refs/heads/mxm-o04-*'],['refs/heads/mxm-o04-active-v1'])):
            route=Route();read=route.json
            def changed(path):
                value=read(path)
                if path=='rulesets/25222248':value['conditions']['ref_name']={'include':include,'exclude':exclude}
                return value
            route.json=changed
            with self.subTest(include=include,exclude=exclude),self.assertRaises(LabError):self.check(route)

