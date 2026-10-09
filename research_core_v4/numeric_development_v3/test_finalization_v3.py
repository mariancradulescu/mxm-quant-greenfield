import ast
import os
import pathlib
import unittest
from unittest.mock import patch
from research_core_v4.numeric_development_v3 import finalization_v3 as f, authority_v3 as a
from research_core_v4.numeric_development_v2 import machine_v2 as v2
from research_core_v4.numeric_development_v1 import numeric_machine_entrypoint_v1 as old
from research_core_v4.numeric_development_v1.public_output_guard_v1 import PublicDisclosureDenied, ROOT as PUB

class Finalization(unittest.TestCase):
    def store(self):
        arm=a.candidate("a"*40,{})
        with patch.dict(os.environ,{"GITHUB_RUN_ID":"123"}):
            return f.Store("a"*40,None,None,None,arm,"b"*64,"c"*64)
    def test_no_ref_means_no_global_pass(self):
        with patch.object(v2,"existing_ref",return_value=[]),patch.object(old,"api") as api:
            self.assertIsNone(f.verify_complete(self.store()))
        api.assert_not_called()
    def test_actual_new_blob_callsite_rejects_private_values(self):
        s=self.store()
        with patch.object(old,"api") as api,self.assertRaises(PublicDisclosureDenied):
            s.publish_exact({**v2.safe_status("a"*40,"FINAL","PASS"),"private_vector":[1]},PUB+"REAL_DEVELOPMENT_COMPLETION_V1.json")
        api.assert_not_called()
    def test_no_in_place_v2_change_and_exact_reducer_reuse(self):
        tree2=ast.parse((old.ROOT/'research_core_v4/numeric_development_v2/machine_v2.py').read_text())
        tree3=ast.parse((old.ROOT/'research_core_v4/numeric_development_v3/machine_v3.py').read_text())
        def reducer(t):
            run=next(x for x in t.body if isinstance(x,ast.FunctionDef) and x.name=='run')
            return next(x for x in ast.walk(run) if isinstance(x,ast.For) and isinstance(x.target,ast.Name) and x.target.id=='idx')
        self.assertEqual(ast.dump(reducer(tree2)),ast.dump(reducer(tree3)))
        imports=[x for x in tree3.body if isinstance(x,ast.ImportFrom)]
        self.assertTrue(any(x.module=='research_core_v4.numeric_development_v2.machine_v2' and any(y.name=='complete_report' for y in x.names) for x in imports))
        final_ast=ast.parse(pathlib.Path(f.__file__).read_text())
        self.assertFalse(any(isinstance(x,ast.Attribute) and x.attr in ('consume_shard','finish') for x in ast.walk(final_ast)))
    def test_original_one_use_identity_is_preserved(self):
        from research_core_v4.numeric_development_v2 import authority_v2
        self.assertEqual(a.candidate("a"*40,{})['invocation_id'],authority_v2.candidate("b"*40,{})['invocation_id'])
        self.assertEqual(v2.claim_name(a.candidate("a"*40,{})),v2.claim_name(authority_v2.candidate("b"*40,{})))
    def test_real_paths_are_successors_and_approval_absent(self):
        self.assertTrue(a.APPROVAL.endswith('numeric_development_v3/INDEPENDENT_ACCEPTANCE_V3.json'))
        self.assertFalse((a.ROOT/a.APPROVAL).exists())
        self.assertEqual(self.store().paths(),(PUB+'REAL_DEVELOPMENT_DELIVERY_V1.json',PUB+'REAL_DEVELOPMENT_COMPLETION_V1.json'))
    def test_finalization_claim_follows_all_readbacks(self):
        text=pathlib.Path(f.__file__).read_text()
        finish=text[text.index('def finish('):]
        self.assertLess(finish.index('FINAL_OUTPUT_READBACK'),finish.index('old.api("git/refs"'))
        self.assertLess(finish.index('FINAL_RELEASE_READBACK'),finish.index('old.api("git/refs"'))
        self.assertLess(finish.index('"completion")'),finish.index('old.api("git/refs"'))

if __name__=='__main__':unittest.main(verbosity=2)
