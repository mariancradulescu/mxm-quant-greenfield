"""Storage IO must precede final native lifetime checks, never extend a lease."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]/'research_core_v4/native_tick_replay_v1/csharp'
class Integration(unittest.TestCase):
 def test_reload_follows_account_and_precedes_all_final_lifetime_checks(self):
  s=(ROOT/'MxmReferenceProductBot.cs').read_text();p=s[s.index('void ApplyPortfolioDecision'):s.index('sealed record NativeRiskMark')]
  self.assertLess(p.index('entryCheckpoint.VerifyPreparedCurrent()'),p.index('double finalNewStopRisk='))
  tail=p[p.index('entryCheckpoint.VerifyPreparedCurrent()'):]
  self.assertLess(tail.index('riskObservationLease.Verify('),tail.index('entryCheckpoint.MarkSubmitted()'))
  self.assertLess(tail.index('var submissionClock=BrokerClock()'),tail.index('entryCheckpoint.MarkSubmitted()'))
  self.assertLess(tail.index('entryCheckpoint.MarkSubmitted()'),tail.index('ExecuteMarketOrder('))
 def test_verification_never_writes_or_clears_persistent_intent(self):
  s=(ROOT/'MxmEntryCheckpoint.cs').read_text();p=s[s.index(' public bool VerifyPreparedCurrent()'):s.index(' public bool MarkSubmitted()')]
  self.assertIn('store.Read()==pending',p);self.assertIn('!Halted',p)
  self.assertNotIn('store.Write',p);self.assertNotIn('WriteVerified',p)
