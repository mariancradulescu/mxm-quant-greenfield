from .test_v1 import CausalExitTests
import unittest
from .collector_v2 import uncovered
class ExistingCoverageTests(unittest.TestCase):
 def test_previously_complete_intervals_are_never_requested(self):self.assertEqual(uncovered(0,100,[(0,10),(90,100)]),[(11,89)])
 def test_overlapping_saved_windows_merge(self):self.assertEqual(uncovered(0,100,[(20,50),(30,70),(71,100)]),[(0,19)])
 def test_empty_authentic_window_is_still_covered(self):self.assertEqual(uncovered(0,100,[(0,100)]),[])
if __name__=='__main__':unittest.main()
