import unittest,sqlite3
from . import archive_v2 as ar
from .runner_v2 import quote_ops
class CoverageRepairTests(unittest.TestCase):
 def setUp(self):self.db=ar.dbopen(":memory:");self.db.execute("CREATE TABLE wire(s INTEGER,k TEXT,a INTEGER,b INTEGER,z TEXT,h TEXT,PRIMARY KEY(s,k,a,b))")
 def tearDown(self):self.db.close()
 def test_partial_prefix_is_work_and_confirmed_suffix_is_not(self):
  ar.span(self.db,1,"bid",0,99,"PARTIAL_HASMORE");ar.span(self.db,1,"bid",51,99,"CONFIRMED_COMPLETE");ar.span(self.db,1,"bid",50,50,"PARTIAL_HASMORE_BOUNDARY_UNRESOLVED")
  self.assertEqual(ar.missing(self.db,1,"bid",0,99),[(0,50)])
  self.assertEqual(ar.actionable(self.db,1,"bid",0,99),[(0,49)])
 def test_uncertain_and_provider_are_missing_but_blocked_for_resend(self):
  for state in ("UNCERTAIN_WIRE","PROVIDER_ERROR_RATE","UNKNOWN_TRANSPORT"):
   self.db.execute("DELETE FROM span");ar.span(self.db,1,"bid",0,99,state)
   self.assertEqual(ar.missing(self.db,1,"bid",0,99),[(0,99)])
   self.assertEqual(ar.actionable(self.db,1,"bid",0,99),[])
 def test_empty_is_no_update_proof_and_does_not_imply_closed_session(self):
  ar.span(self.db,1,"bid",0,99,"EMPTY_AUTHENTIC_RESPONSE")
  self.assertEqual(ar.category("EMPTY_AUTHENTIC_RESPONSE"),"EMPTY_AUTHENTIC_RESPONSE");self.assertEqual(ar.missing(self.db,1,"bid",0,99),[])
 def test_overlap_union_issues_one_interval_per_side(self):
  ops=quote_ops(self.db,{(1,1800),(1,2700)})
  self.assertEqual(len(ops),2);self.assertEqual({(r["a"],r["b"]) for r in ops},{(0,2700000)})
 def test_accepted_exact_request_is_not_reissued(self):
  self.db.execute("INSERT INTO wire VALUES(1,'bid',0,1800000,'PARTIAL_HASMORE',NULL)")
  ops=quote_ops(self.db,{(1,1800)})
  self.assertTrue(all(r["k"]!="bid" for r in ops))
if __name__=="__main__":unittest.main()

