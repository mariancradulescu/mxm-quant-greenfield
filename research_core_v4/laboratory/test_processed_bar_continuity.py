"""A platform array may backfill bars whose callbacks never reached the Robot."""
import json,os,shutil,subprocess,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PROJECT=ROOT/'research_core_v4/laboratory/csharp/processed_bars/MxmProcessedBars.csproj'
def bar(k,symbol='a',platform_adjacent=True):
 return dict(symbol=symbol,utc=(datetime(2026,10,26,tzinfo=timezone.utc)+timedelta(minutes=5*k)).isoformat().replace('+00:00','Z'),platform_adjacent=platform_adjacent,close=100+k)
class Compiled(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  if not shutil.which('dotnet'):
   if os.environ.get('GITHUB_ACTIONS')=='true':raise RuntimeError('Compiled continuity test required')
   raise unittest.SkipTest('CSharp required in CI')
 def run_bars(self,bars):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'in').write_text(json.dumps(dict(symbols=['a','b'],bars=bars)))
   r=subprocess.run(['dotnet','run','--project',str(PROJECT),'-c','Release','--no-build','--',str(p/'in'),str(p/'out')],capture_output=True,text=True)
   self.assertEqual(r.returncode,0,r.stderr);return json.loads((p/'out').read_bytes())
 def test_backfilled_adjacent_array_cannot_bridge_missed_callbacks(self):
  r=self.run_bars([bar(k) for k in range(6)]+[bar(10),bar(11)])
  self.assertEqual([x['count'] for x in r],[1,2,3,4,5,6,1,2])
  self.assertFalse(r[6]['contiguous']);self.assertEqual(r[6]['decision'],0)
 def test_platform_gap_also_resets_and_symbols_have_separate_history(self):
  r=self.run_bars([bar(0),bar(1,'b'),bar(1),bar(2,platform_adjacent=False),bar(2,'b')])
  self.assertEqual([x['count'] for x in r],[1,1,2,1,2])
 def test_duplicate_and_reordered_callbacks_do_not_advance_predecessor(self):
  r=self.run_bars([bar(0),bar(1),bar(1),bar(0),bar(2)])
  self.assertEqual([x['accepted'] for x in r],[True,True,False,False,True])
  self.assertEqual(r[-1]['count'],3);self.assertTrue(r[-1]['contiguous'])
 def test_new_instance_rewarms_and_non_utc_is_rejected(self):
  self.assertEqual(self.run_bars([bar(100)])[0]['count'],1)
  a=bar(0);a['utc']=a['utc'].removesuffix('Z');r=self.run_bars([a,bar(1)])
  self.assertFalse(r[0]['accepted']);self.assertFalse(r[1]['contiguous'])
class Integration(unittest.TestCase):
 def test_native_uses_processed_callback_and_platform_predecessor_before_kernel(self):
  s=(ROOT/'research_core_v4/native_tick_replay_v1/csharp/MxmReferenceProductBot.cs').read_text()
  p=s[s.index('void OnPortfolioBarClosed'):s.index('void OnPortfolioTick')]
  self.assertIn('BarMinutes,out bool processedContiguous,out var reason',p)
  self.assertIn('bool contiguous=processedContiguous &&',p)
  self.assertLess(p.index('if(!contiguous){kernel.Reset();causalIntents[instrumentName].Clear();}'),p.index('kernel.OnCompletedBar'))
