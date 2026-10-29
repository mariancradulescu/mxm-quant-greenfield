"""Recovered PR104 contracts against the actual adapter, without custody or economics."""
import ast
import unittest
from pathlib import Path
from .common import need,LabError

PATH=Path('research_core_v4/laboratory/chronology_csharp_bridge.py')
def actual_helper():
    tree=ast.parse(PATH.read_text())
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='quote_update_gap_witness')
    scope={'need':need}
    exec(compile(ast.Module(body=[function],type_ignores=[]),str(PATH),'exec'),scope)
    return scope['quote_update_gap_witness']

class GapRecoveryTests(unittest.TestCase):
    def test_edges_and_same_ms_revisions(self):
        r=actual_helper()([(1000,11),(1000,12),(7000,13),(71001,14)],0,100000)
        self.assertEqual((r['quote_updates'],r['distinct_update_ms']), (4,3))
        self.assertEqual(r['longest_no_update_interval_ms'],64001)
        self.assertEqual((r['intervals_over_5s'],r['intervals_over_60s']),(3,1))
        self.assertEqual((r['first_update_delay_ms'],r['last_update_to_window_end_ms']),(1000,28999))
    def test_empty_side_and_invalid_windows(self):
        f=actual_helper();r=f([],0,100000)
        self.assertEqual(r['longest_no_update_interval_ms'],100000)
        self.assertIsNone(r['first_update_delay_ms'])
        self.assertIsNone(r['last_update_to_window_end_ms'])
        for rows in ([(5,1),(4,1)],[(100000,1)],[(-1,1)],[(True,1)]):
            with self.assertRaises(LabError):f(rows,0,100000)
        with self.assertRaises(LabError):f([],0,0)
    def test_actual_export_binds_both_sides_to_native_window_after_verification(self):
        text=PATH.read_text();tree=ast.parse(text)
        export=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='export')
        calls=[n for n in ast.walk(export) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='quote_update_gap_witness']
        self.assertEqual(len(calls),2)
        self.assertEqual({ast.unparse(n.args[0]) for n in calls},{'bid','ask'})
        for call in calls:
            self.assertEqual(ast.unparse(call.args[1]),"native.POLICY['from_ms']")
            self.assertEqual(ast.unparse(call.args[2]),"native.POLICY['to_ms']")
            self.assertGreater(call.lineno,next(n.lineno for n in ast.walk(export) if isinstance(n,ast.Assign) and any(isinstance(x,ast.Tuple) and any(isinstance(a,ast.Name) and a.id=='ask' for a in x.elts) for x in n.targets)))
        self.assertIn("'continuous_market_coverage_proven':False",text)
        self.assertIn("'economic_outcomes':0",text)
        self.assertIn('NOT_MARKET_CLOSURE_OR_HISTORICAL_ARRIVAL',text)

if __name__=='__main__':unittest.main()

