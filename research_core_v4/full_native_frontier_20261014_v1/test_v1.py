import unittest
from .kernel_v1 import quote_state,feature,schedule_clocks
from . import archive_v1 as archive
import tempfile,pathlib
class Checks(unittest.TestCase):
 def test_exact_completed_window_not_repeated(self):
  with tempfile.TemporaryDirectory() as d:
   db=archive.dbopen(pathlib.Path(d)/'state.sqlite');archive.span(db,1,'bid',1000,2000,'ARCHIVED_COMPLETE_RESPONSE');self.assertEqual(archive.missing(db,1,'bid',0,3000),[(0,999),(2001,3000)])
 def test_source_imports_and_syntax(self):
  from .runner_v1 import FrontierStore
  self.assertTrue(callable(FrontierStore.restore))
 def test_no_lookahead(self):
  a=quote_state([(1000,100000),(4000,200000)],[(1000,100100)],2000)
  self.assertEqual(a['bid'],1)
 def test_no_fabricated_seed(self):self.assertFalse(quote_state([],[(1000,100100)],2000)['valid'])
 def test_conflict_and_expiry(self):
  self.assertFalse(quote_state([(1000,100000),(1000,100002)],[(1000,100100)],2000)['valid']);self.assertFalse(quote_state([(1,100000)],[(1,100100)],301000)['valid'])
 def test_freshness_distinction(self):
  self.assertFalse(quote_state([(1,100000)],[(10000,100100)],11000,5000,2000)['valid']);self.assertTrue(quote_state([(1,100000)],[(10000,100100)],11000)['valid'])
 def test_future_bar_not_feature(self):
  bars={i*300:[1,1.1,.9,1,1] for i in range(30)};a=feature(bars,5000,0,'CONTROL');bars[6000]=[100,1000,.1,1,100];self.assertEqual(a,feature(bars,5000,0,'CONTROL'))
 def test_dst_real_native_timezone(self):
  f={'scheduleTimeZone':'America/New_York','schedule':[{'startSecond':1*86400+9*3600+1800,'endSecond':1*86400+16*3600}]};x=schedule_clocks(f,1772323200,1773532800);self.assertGreater(len(x),0)
if __name__=='__main__':unittest.main()
