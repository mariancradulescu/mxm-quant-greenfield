import json,os,random,shutil,subprocess,tempfile,unittest
from pathlib import Path
from .support_topology_reference import reference,summarize
ROOT=Path(__file__).resolve().parents[2]
PROJECT=ROOT/'research_core_v4/laboratory/csharp/support_topology/MxmSupportTopology.csproj'
class Compiled(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  if not shutil.which('dotnet'):
   if os.environ.get('GITHUB_ACTIONS')=='true':raise RuntimeError('Compiled support topology required')
   raise unittest.SkipTest('CSharp required in CI')
 def compute(self,packets,valid=True):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'in').write_text(''.join(json.dumps(x)+'\n' for x in packets))
   r=subprocess.run(['dotnet','run','--project',str(PROJECT),'-c','Release','--no-build','--',str(p/'in'),str(p/'out')],capture_output=True,text=True)
   if not valid:self.assertNotEqual(r.returncode,0);return
   self.assertEqual(r.returncode,0,r.stderr);a=json.loads((p/'out').read_bytes());self.assertEqual(a,reference(packets));return a
 def test_empty_and_complete_source_all_blocks_and_boundary_censoring(self):
  a=self.compute([dict(ordinal=1,slots=[]),dict(ordinal=2,slots=list(range(8064)))])
  self.assertEqual(a['Rows'],8064)
  self.assertEqual(a['Cells'][-1]['OutsideArchive'],289)
  self.assertEqual(a['Cells'][-1]['MissingInterior'],0)
 def test_internal_missing_entry_exit_and_path_are_not_healed(self):
  a=self.compute([dict(ordinal=1,slots=[k for k in range(90) if k not in (20,31,45)])])
  cells=a['Cells'];self.assertGreater(cells[1]['MissingInterior'],0)
  self.assertGreater(cells[0]['MissingEntry'],0);self.assertGreater(cells[0]['MissingExit'],0)
 def test_random_irregular_support_and_segment_crossings(self):
  rng=random.Random(29028)
  self.compute([dict(ordinal=i+1,slots=[k for k in range(8064) if rng.random()<p]) for i,p in enumerate((.2,.7,.99))])
 def test_reject_unknown_prices_unsorted_duplicate_and_outside_archive(self):
  for p in (dict(ordinal=1,slots=[1,1]),dict(ordinal=1,slots=[2,1]),dict(ordinal=1,slots=[8064]),dict(ordinal=1,slots=[1],open='100')):
   self.compute([p],False)
  self.compute([dict(ordinal=1,slots=[])]*2,False)
class Scope(unittest.TestCase):
 def test_unselected_grid_is_not_strategy_or_temporal_return_qualification(self):
  s=summarize(reference([dict(ordinal=1,slots=list(range(8064)))]))
  self.assertEqual(s['new_strategy_identities'],0);self.assertTrue(s['return_stability_not_measured'])
  self.assertTrue(s['support_does_not_identify_signal_conditioned_censoring'])
 def test_frozen_source_roles_and_no_closed_economic_evaluator(self):
  from . import support_topology_reception as n
  n.validate();w=n.workflow();self.assertEqual(json.loads((ROOT/n.PATH).read_bytes()),w)
  self.assertNotIn('workflow_dispatch',w['on']);self.assertNotIn('R3_CTRADER_',json.dumps(w))
  self.assertNotIn('SUCCESSOR_APP_PRIVATE_KEY',json.dumps(w))
  self.assertEqual(n.POLICY['new_strategy_identities'],0)
 def test_wrong_context_fails_before_git_source_or_keys(self):
  from . import support_topology_reception as n
  from unittest.mock import patch
  with patch.dict(os.environ,{},clear=True),patch.object(n.subprocess,'check_output') as git:
   with self.assertRaises(ValueError):n.context(True)
   git.assert_not_called()
